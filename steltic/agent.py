import re
"""The headless agent loop, ported to a generic OpenAI-compatible endpoint and streamed as events.

run_design(...) is a SYNC GENERATOR that yields event dicts (token / step / tool / tool_result /
assistant / status / done / error). FastAPI serves them as Server-Sent Events. The model's run_python
calls go to the sandbox executor; all other tools are controlled backend ops on the session job dir.

A MOCK model (model == "MOCK") runs a short scripted sequence that exercises the full pipe
(auth -> job workspace -> sandbox -> stream) without any LLM, so the app is testable offline.
"""
import json, os, time, hashlib
import httpx
from . import config, contract
from .sandbox import is_blocked


class LLMHTTPError(RuntimeError):
    """An HTTP error from the LLM endpoint. `retryable` is False for 4xx client/config errors (a bad
    request won't succeed on retry); True for 408/429/5xx transient errors."""
    def __init__(self, msg, retryable=True):
        super().__init__(msg)
        self.retryable = retryable


class _ThinkSplitter:
    """Some providers (DeepSeek via vLLM / Azure AI Foundry) stream the chain-of-thought INLINE in `content`
    wrapped in <think>...</think>, not in a separate `reasoning` field. This routes the think spans to
    'reasoning' and the rest to 'token' (safe across deltas that split a tag) and strips the tags so they
    never land in the stored answer."""
    OPEN, CLOSE = "<think>", "</think>"
    def __init__(self):
        self.in_think = False
        self.buf = ""
    def feed(self, text):
        self.buf += text
        out = []
        while self.buf:
            tag = self.CLOSE if self.in_think else self.OPEN
            kind = "reasoning" if self.in_think else "token"
            idx = self.buf.find(tag)
            if idx == -1:                                   # no complete tag -> emit all but a possible partial-tag tail
                safe = self._safe(self.buf, tag)
                if safe:
                    out.append((kind, self.buf[:safe])); self.buf = self.buf[safe:]
                break
            if idx:
                out.append((kind, self.buf[:idx]))
            self.buf = self.buf[idx + len(tag):]
            self.in_think = not self.in_think
        return out
    def flush(self):
        t, self.buf = self.buf, ""
        return ("reasoning" if self.in_think else "token", t) if t else None
    @staticmethod
    def _safe(buf, tag):                                    # longest suffix of buf that could start `tag` -> hold it back
        for k in range(min(len(tag) - 1, len(buf)), 0, -1):
            if buf.endswith(tag[:k]):
                return len(buf) - k
        return len(buf)


def _spec(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}

TOOL_SPECS = [
    _spec("new_activity_log", "Start a fresh activity log for a design run (call ONCE first).",
          {"building": {"type": "string", "description": "building name -> jobs/<name>/"}}, []),
    _spec("search_engineering_standards",
          "Retrieve a provision from the India standards corpus UNDER THE RETRIEVAL POLICY (contract/QUERYING_IS_CORPUS.md): "
          "one document per call, an EXACT id when you know the provision (type=exact_section|exact_table and "
          "query=the id ALONE, e.g. 6.6.1.1, 5.2.1.1, 8.1, table 9), and a full-text query (type=fts) only "
          "to NAVIGATE to an id -- in the standard's own printed words, one idea, no sentences. "
          "Good: {type:'exact_section', doc:'IS_801_1975', query:'6.5'}. "
          "Bad: {query:'IS 801 web crippling of single unreinforced webs at end reactions 6.5'}. "
          "Documents: IS_801_1975 (CFS members -- primary), IS_811_1987 (sections), "
          "LOAD stems IS_875_Part_* + IS_1893_Part_1_2016 MANDATORY every job into cfg[load_plan]; "
          "IS_800_2007 / IS_18168_2023 ONLY with purpose=lateral_frame_is800 (hot-rolled frame) or "
          "serviceability_limits_table6. AISI / ASCE / AISC collections are refused (D3). No worked-example collection "
          "is ingested for India. Returns a 'disabled' note if no RAG is configured -- then rely on your own cited "
          "IS 801/811 knowledge. Loads must still go through load_plan.",
          {"query": {"type": "string", "description": "for exact types: the id only. For fts: printed spec terminology, one idea."},
           "type": {"type": "string", "enum": ["exact_section", "exact_equation", "exact_table", "fts"],
                    "description": "exact_section (6.6.1.1, 5.2.1.1, 8.1) / exact_table (2, 9, 6) / fts (navigation only)"},
           "doc": {"type": "string", "description": "canonical document stem: IS_801_1975, IS_811_1987, IS_875_Part_1_2026 .. IS_875_Part_5_1987, IS_1893_Part_1_2016, IS_800_2007, IS_18168_2023. One per call."},
           "purpose": {"type": "string", "description": "why you need it (provenance). Required allowlisted value if doc/collection is IS_800_2007 / IS_18168_2023: lateral_frame_is800 | serviceability_limits_table6 | sfrs_gap_found_false | document_absence | found_false_log | eor_documented_exception (C6 refusal otherwise)."},
           "want_commentary": {"type": "boolean", "description": "default false (provisions). true only for intent/background; commentary never supplies a design value."},
           "context_neighbors": {"type": "integer", "description": "0-2: widen when an equation needs its surrounding 'where:' list"},
           "collection": {"type": "string",
                          "description": "legacy alias of doc (engineering_standards_IS801 / _IS811 / _IS875_P* / _IS1893 / _IS800 gated)"},
           "clause": {"type": "string", "description": "legacy: an exact id sent with a sentence. Prefer type + query=id."},
           "chapter": {"type": "string", "description": "optional: narrow an fts query to a top-level section, e.g. 6 (design), 7 (connections), 8 (bracing)"},
           "top_k": {"type": "integer", "description": "chunks to return (default 3, max 5)"}},
          ["query"]),
    _spec("run_python",
          "Execute Python in an ISOLATED SANDBOX with the steel engine importable and cwd=jobs/<name>/. "
          "Drive pipeline.design_and_report(name, cfg). No network, no installs.",
          {"code": {"type": "string", "description": "Python source to execute"}}, ["code"]),
    _spec("write_file", "Write a file into the workspace (e.g. jobs/<name>/cfg.py). Never hand-write design/calc_package_cfs.json.",
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _spec("read_file", "Read a file (job workspace or engine source). Returns <=600 lines; paginate with offset/limit.",
          {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, ["path"]),
    _spec("list_files", "List a workspace directory.", {"path": {"type": "string"}}, []),
    _spec("activity_summary", "Summary of the activity log (counts per tool + records).", {}, []),
]


# ---------------- tool dispatch ----------------
def _prune_rag(messages, keep=2):
    """Replace all but the most recent `keep` RAG tool results with a stub -- the agent has already
    lifted the cited clause into calc_package.json, so the raw chunks are dead weight in the history.
    Keeps the tool_call_id linkage intact; once stubbed a result stays stubbed (stable for caching)."""
    if keep <= 0:
        return
    STUB = "[earlier RAG result pruned to save context -- its clause is in calc_package.json; re-search if needed]"
    idx = [i for i, m in enumerate(messages)
           if m.get("role") == "tool" and m.get("name") == "search_engineering_standards"
           and isinstance(m.get("content"), str) and not m["content"].startswith("[earlier RAG result pruned")]
    for i in (idx[:-keep] if keep > 0 else idx):
        messages[i] = {**messages[i], "content": STUB}


_RAG_SAVED   = re.compile(r'"saved"\s*:\s*"([^"]+)"')           # recover the eviction pointer from a truncated/invalid-JSON
_RAG_QUERY   = re.compile(r'"query"\s*:\s*"((?:[^"\\]|\\.)*)"')  # spec result -- _save_rag emits these keys FIRST, so they
_RAG_CLAUSES = re.compile(r'"clauses_found"\s*:\s*\[([^\]]*)\]') # survive the output cap even when the hits get cut off


def _unescape_json(s):
    try:
        return json.loads('"' + s + '"')
    except Exception:
        return s


def _evict_all_rag(messages):
    """Called once a design COMPLETES: replace every filed spec-RAG tool result with a tiny pointer to its
    saved rag/<slug>.txt, so the conversation a later Continue/optimisation reloads doesn't carry the raw
    chunks. Lossless -- the full text is on disk and the stub keeps query + clause codes + path. Only results
    that were saved to a file are touched (OpenSees/inline results are small and left as-is). Robust to the
    output cap: if a large result was truncated to invalid JSON, the saved/query/clauses_found keys (emitted
    FIRST by _save_rag) are recovered by regex so it still gets evicted."""
    for i, m in enumerate(messages):
        if m.get("role") != "tool" or m.get("name") != "search_engineering_standards":
            continue
        c = m.get("content")
        if not isinstance(c, str) or c.startswith("[RAG pruned"):
            continue
        try:
            d = json.loads(c)
            saved = d.get("saved")
            if not saved:
                continue                               # inline (e.g. OpenSees/example) result -- leave it
            query = d.get("query", "")
            clauses = ", ".join((d.get("clauses_found") or [])[:12]) or "n/a"
        except Exception:
            ms = _RAG_SAVED.search(c)                  # truncated/invalid JSON -- recover the pointer by regex
            if not ms:
                continue                               # not a saved spec result -- leave it
            saved = ms.group(1)
            mq = _RAG_QUERY.search(c)
            query = _unescape_json(mq.group(1)) if mq else ""
            mc = _RAG_CLAUSES.search(c)
            clauses = (", ".join(re.findall(r'"([^"]+)"', mc.group(1))[:12]) if mc else "") or "n/a"
        messages[i] = {**m, "content":
            f"[RAG pruned after design completion -- query: {query!r}; clauses: {clauses}; "
            f"full text in {saved}. read_file('{saved}') if a later step needs a clause from it.]"}



# ---------------- hardening #1: R21 enforced in the TOOL, not just the contract ----------------
_OS_ERR = re.compile(r"(ArpackSolver|genBand|failed to do eigen|Eigen failed|analysis failed|"
                     r"singular matrix|LinearSOE|Umfpack|rigidDiaphragm.*fail|failed to add node|"
                     r"OpenSees.*error)", re.I)
_R21_TABLE = ("R21 - the OpenSees docs RAG exists for exactly this. error -> cause -> what to pull:\n"
    "- ArpackSolver/_saupd/genBand/'failed to do eigen' -> mechanism or ZERO mass at active DOFs, or "
    "numEigen > nonzero-mass DOFs -> mass at EVERY diaphragm master; reduce numEigen; "
    "eigen('-fullGenLapack', n) for small/ill-conditioned models. Query: eigen, mass.\n"
    "- LinearSOE/Umfpack/'singular' -> unrestrained DOF, disconnected node, missing girder, "
    "out-of-plane instability -> check supports/releases; add the missing member. Query: constraints, node/fix.\n"
    "- rigidDiaphragm/'failed to add' -> constraint-handler mismatch; master missing mass; releasing a "
    "constrained DOF -> constraints('Transformation'); do NOT release diaphragm DOFs. Query: rigidDiaphragm.\n"
    "- KeyError 'heights_m'/'lateral_frame'/'cfs_members'/is811_sections.* -> FRAMEWORK-API guess, not OpenSees -> re-read the "
    "India cfg schema in AGENT_START and india_cfs_lateral / india_cfs_portal docstrings (fixtures: tests/fixtures/IN_CFS_Ex1, Ex5).")


def _r21_track(ws, result):
    """Update the consecutive-OpenSees-error streak on the workspace; annotate erroring results."""
    txt = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
    if _OS_ERR.search(txt or ""):
        ws._os_err_streak = getattr(ws, "_os_err_streak", 0) + 1
        ws._os_docs_since_err = False
        if isinstance(result, dict):
            result["r21"] = ("OpenSees error #%d in a row. %s" % (ws._os_err_streak,
                             "You MUST query openseespy_documentation / opensees_documentation before "
                             "the next run_python (the tool will refuse a 3rd blind retry).\n" + _R21_TABLE
                             if ws._os_err_streak >= 2 else
                             "If the next attempt also fails, query openseespy_documentation for the "
                             "failing command before retrying (R21)."))
    elif isinstance(result, dict) and result.get("returncode") == 0:
        ws._os_err_streak = 0
        ws._os_docs_since_err = True
    return result


def _r21_gate(ws, code):
    """Refuse the 3rd consecutive blind run_python after OpenSees errors until the docs RAG is queried."""
    if getattr(ws, "_os_err_streak", 0) >= 2 and not getattr(ws, "_os_docs_since_err", True):
        return {"blocked": "R21 gate: the last %d run_python calls hit OpenSees errors and you have not "
                           "queried the OpenSees docs RAG. Call search_engineering_standards with "
                           "collection='openseespy_documentation' (or 'opensees_documentation') for the "
                           "failing command FIRST, then fix and re-run.\n" % ws._os_err_streak + _R21_TABLE}
    return None



# ---------------- hardening #2: blocking completion gate (app-side; India package schema) ----------------
def _completion_gate(ws):
    """Checks on jobs/<building>/design/calc_package_cfs.json before a final answer is accepted. Returns a list of
    problems ([] = clean). The ONE authority is india_cfs_gates.design_status (D3 / WP3.6): the package's stored status
    is re-derived here from the cfg snapshot and the package, so a hand-edited package cannot claim COMPLETE. A slot
    carrying 'waived' is a problem, never a pass."""
    import pathlib
    probs = []
    try:
        jd = ws._job_dir() if hasattr(ws, "_job_dir") else None
        if not jd:
            return []
        cp = pathlib.Path(jd) / "design" / "calc_package_cfs.json"
        if not cp.exists():
            if (pathlib.Path(jd) / "design" / "calc_package.json").exists():
                return ["design/calc_package.json is the removed US wall-path package (D3) -- run pipeline.design_and_report "
                        "with the India cfg; the India package is design/calc_package_cfs.json"]
            return ["design/calc_package_cfs.json does not exist -- run pipeline.design_and_report first"]
        pkg = json.loads(cp.read_text(errors="replace"))
        try:
            import sys as _sys
            _se = str(pathlib.Path(__file__).resolve().parents[1] / "steel_engine")
            if _se not in _sys.path:
                _sys.path.insert(0, _se)
            import india_cfs_env  # noqa: F401
            import india_cfs_gates as _ICG
            _cfg = pkg.get("cfg_snapshot") if isinstance(pkg.get("cfg_snapshot"), dict) else {}
            if not _cfg:
                _snap = pathlib.Path(jd) / "cfg_snapshot.json"
                if _snap.exists():
                    _cfg = json.loads(_snap.read_text(errors="replace"))
            st = _ICG.design_status(_cfg, pkg)
            stored = (pkg.get("design_status") or {}).get("status")
            if stored and stored != st.get("status"):
                probs.append("package claims design_status %r but india_cfs_gates.design_status re-derives %r -- the package "
                             "was edited by hand; re-run pipeline.design_and_report" % (stored, st.get("status")))
            if st.get("status") != "complete":
                for r in (st.get("reasons") or [])[:10]:
                    probs.append("design_status %s: %s" % (st.get("status"), r))
        except Exception as _e:
            probs.append("India design_status gate error: %s" % _e)
        # ---- deliverable completeness (independent of the gate) ----
        for label, key in (("cfs member", "cfs_members"), ("diaphragm", "diaphragm")):
            for x in pkg.get(key) or []:
                if isinstance(x, dict) and x.get("waived"):
                    probs.append("%s '%s' is waived -- waivers are not permitted (fix the design)" % (label, x.get("id") or x.get("storey")))
        lat = pkg.get("lateral_frame") or {}
        if not lat:
            probs.append("no lateral_frame in the package -- the D3 hot-rolled frame (or the elastic all-CFS portal) was not run")
        elif not (lat.get("connections") or pkg.get("cfs_connections")):
            probs.append("connections list is EMPTY -- frame / portal connections and bases are a required deliverable")
        if not pkg.get("cfs_members"):
            probs.append("cfs_members is EMPTY -- studs / joists / purlins / girts are the CFS deliverable")
        if pkg.get("consistency"):
            probs.append("consistency flags unresolved: %s" % "; ".join(map(str, pkg["consistency"][:4])))
    except Exception as e:
        return ["completion gate could not read calc_package_cfs.json: %s" % e]
    return probs[:12]



# hardening #7: phase-sliced contract hints -- tiny, in-context, fired at most once each.
_PHASE_HINTS = (
    ("units", re.compile(r"look like FEET|look like INCHES|units.*must be 'm'", re.I),
     "UNITS: the India cfg is METRES / kN/m2 (cfg['units']='m'); the engines convert to N-mm themselves. Fix the "
     "cfg and re-run design_and_report BEFORE chasing analysis numbers."),
    ("preflight", re.compile(r"\[preflight\].*\[ERROR\]", re.S),
     "PREFLIGHT ERRORS above are cfg mis-declarations (banned US keys, a foreign lateral system, an SFIA label, a missing "
     "site / occupancy / load or k2 table) -- fix them in cfg.py and re-run the pipeline before anything else."),
    ("system", re.compile(r"LateralSystemError|not permitted in Zone|IS 18168", re.I),
     "LATERAL SYSTEM: the D3 / L7 system for the zone is enforced (II OCBF R 4.0; III-V SCBF R 4.5; EBF R 5.0; SMRF "
     "portal only h < 15 m; IS 18168 1.3 forbids SCBF in Zone V). Set lateral_frame.system / R to the resolved system."),
    ("driftfail", re.compile(r"drift.*(fail|exceed)|0\.004", re.I),
     "DRIFT: IS 1893 7.11.1 storey drift <= 0.004 h at VB (gamma 1.0); portals also IS 800 Table 6 h/150 at 1.0 W. "
     "Stiffen the frame (deeper columns, X-bracing in more bays, fixed bases, knee braces on a portal); never raise "
     "cfg['drift_limit'] and never declare a storey exempt."),
    ("eor", re.compile(r"EOR input|not in corpus|found:false", re.I),
     "EOR INPUT / found:false: declare the value in cfg['eor_inputs'] with its formula, source and 'VERIFY', or cite a "
     "test / product value with basis 'test'. Never fill the gap from memory or from a foreign standard."),
    ("brace_share", re.compile(r"brace_tension_share", re.I),
     "The vendored IS 800 12.8.2.4 brace tension-share check fails where gravity compression dominates a light braced "
     "bay: report it as an open engineering item for the hot-rolled lead (the check should use EQ-only brace forces); "
     "do not waive it and do not resize braces to chase it."),
)


def dispatch(tool, args, ws, executor):
    if tool == "run_python":
        code = args.get("code", "")
        blocked = is_blocked(code)
        if blocked:
            ws.log("run_python", " ".join(code.split())[:120], "refused")
            return {"error": blocked}
        gate = _r21_gate(ws, code)                      # hardening #1: no 3rd blind OpenSees retry
        if gate:
            ws.log("run_python", " ".join(code.split())[:120], "R21-blocked (query the OpenSees docs first)")
            return gate
        res = executor.run(code, ws.jobs, ws.building or "design", config.SANDBOX_TIMEOUT)
        ws.log("run_python", " ".join(code.split())[:120],
               f"rc={res.returncode}" + (" timeout" if res.timed_out else ""))
        return _r21_track(ws, res.to_tool_result())
    if tool == "new_activity_log":
        return ws.new_activity_log(args.get("building", ""))
    if tool == "write_file":
        return ws.write_file(args.get("path", ""), args.get("content", ""))
    if tool == "read_file":
        return ws.read_file(args.get("path", ""), args.get("offset", 0), args.get("limit", 0))
    if tool == "list_files":
        return ws.list_files(args.get("path", "."))
    if tool == "activity_summary":
        return ws.activity_summary()
    if tool == "search_engineering_standards":
        return ws.search_engineering_standards(args.get("query", ""),
                                               args.get("collection", "engineering_standards_IS801"),
                                               args.get("top_k", config.RAG_TOP_K),
                                               args.get("clause", ""), args.get("chapter", ""),
                                               type=args.get("type", ""), doc=args.get("doc", ""),
                                               want_commentary=bool(args.get("want_commentary", False)),
                                               context_neighbors=args.get("context_neighbors"),
                                               purpose=args.get("purpose", ""))
    return {"error": f"unknown tool '{tool}'"}


# ---------------- LLM streaming (generator: yields token events, returns assembled reply) ----------------
def _reasoning_param(mode, base_url):
    """OpenRouter unified reasoning control (effort / enabled). Only sent to openrouter endpoints."""
    if "openrouter" not in (base_url or "") or not mode or mode == "default":
        return None
    if mode == "off":
        return {"enabled": False}
    if mode in ("low", "medium", "high"):
        return {"effort": mode}
    return None


# Learned per-endpoint+model request quirks, so we adapt the payload ONCE (not every call). Filled when an
# endpoint rejects a parameter with a 400 -- e.g. newer OpenAI/Azure models want `max_completion_tokens` and
# reject `temperature`. Keyed (base_url, model); lives for the process (a fresh instance re-learns on 1 call).
_MODEL_QUIRKS: dict = {}


def _build_chat_payload(model, messages, max_tok, reasoning, provider, base_url, quirks):
    p = {"model": model, "messages": messages, "tools": TOOL_SPECS, "tool_choice": "auto", "stream": True}
    p["max_completion_tokens" if "max_completion_tokens" in quirks else "max_tokens"] = max_tok
    if "no_temperature" not in quirks:
        p["temperature"] = config.TEMPERATURE
    if "no_stream_options" not in quirks:
        p["stream_options"] = {"include_usage": True}
    if reasoning:
        p["reasoning"] = reasoning
    if provider and "openrouter" in (base_url or ""):
        p["provider"] = {"order": [provider], "allow_fallbacks": False, "require_parameters": True}
    return p


def _detect_quirk(body):
    """A recoverable 400 -> the payload tweak that fixes it (retry adapted), else None."""
    b = (body or "").lower()
    if "max_completion_tokens" in b or ("max_tokens" in b and ("unsupported" in b or "not supported" in b)):
        return "max_completion_tokens"
    if "temperature" in b and ("unsupported" in b or "not supported" in b or "does not support" in b):
        return "no_temperature"
    if "stream_options" in b and ("unsupported" in b or "not supported" in b):
        return "no_stream_options"
    return None


class UserStop(BaseException):
    """User pressed Stop / client disconnected: raised between streamed tokens so the in-flight
    provider call aborts immediately. BaseException on purpose -- retry/error nets must not swallow it."""


def _stream_chat(base_url, api_key, model, messages, max_tok, reasoning=None, cache=False, provider="", cancel=None):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    api_messages = messages
    if cache and len(messages) >= 2 and isinstance(messages[-1].get("content"), str) and messages[-1]["content"].strip():
        # rolling Anthropic cache breakpoint on the LAST message: the growing conversation prefix is read
        # from cache next turn, so only the newest tokens bill at full price (system prompt already cached).
        api_messages = messages[:-1] + [{**messages[-1], "content": [
            {"type": "text", "text": messages[-1]["content"], "cache_control": {"type": "ephemeral"}}]}]
    quirks = _MODEL_QUIRKS.setdefault((base_url, model), set())
    content_parts, tool_acc, finish, usage, think = [], {}, None, None, _ThinkSplitter()
    with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
        r = None
        for _ in range(4):                                  # adapt the payload on a recoverable 400, then stream
            payload = _build_chat_payload(model, api_messages, max_tok, reasoning, provider, base_url, quirks)
            resp = client.send(client.build_request("POST", url, headers=headers, json=payload), stream=True)
            if resp.status_code < 400:
                r = resp
                break
            body = resp.read().decode("utf-8", "replace")[:1200]
            resp.close()
            q = _detect_quirk(body)
            if q and q not in quirks:                       # learn the param fix; retry adapted (reused next call)
                quirks.add(q)
                continue
            # 4xx (except 408/429) is a client/config error -> fail fast; 408/429/5xx are transient -> retryable.
            retryable = resp.status_code in (408, 429) or resp.status_code >= 500
            raise LLMHTTPError(f"LLM API {resp.status_code}: {body}", retryable=retryable)
        if r is None:
            raise LLMHTTPError("LLM API 400: could not satisfy the model's parameter requirements", retryable=False)
        # Stop watchdog (2026-08-12): the per-line cancel check below only runs when the provider
        # SENDS something -- a model 'thinking' silently leaves the socket open and generation
        # (and billing) running after Stop. This thread polls the cancel flag every second and
        # force-closes the response: the provider sees the disconnect and stops, and the reader
        # below unwinds through UserStop.
        _watch_done = None
        if cancel:
            import threading as _th
            _watch_done = _th.Event()
            def _stop_watch():
                while not _watch_done.wait(1.0):
                    if cancel():
                        # socket.shutdown() is the only call that WAKES a reader blocked in
                        # recv() (close() from another thread does not, POSIX); fall back to
                        # close() if the transport doesn't expose the socket.
                        try:
                            _ns = r.extensions.get("network_stream")
                            _sock = _ns.get_extra_info("socket") if _ns else None
                            if _sock is not None:
                                import socket as _sk
                                _sock.shutdown(_sk.SHUT_RDWR)
                        except Exception:
                            pass
                        try: r.close()
                        except Exception: pass
                        return
            _th.Thread(target=_stop_watch, daemon=True).start()
        try:
            for line in r.iter_lines():
                if cancel and cancel():
                    raise UserStop()     # unwinds the httpx stream context -> provider stops generating
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                if chunk.get("usage"):
                    usage = chunk["usage"]
                ch = (chunk.get("choices") or [{}])[0]
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    for _kind, _txt in think.feed(delta["content"]):   # split inline <think>…</think> out of content
                        if not _txt:
                            continue
                        if _kind == "token":
                            content_parts.append(_txt)
                        yield {"type": _kind, "text": _txt}
                _rt = delta.get("reasoning") or delta.get("reasoning_content") or delta.get("thinking")   # separate-field CoT
                if _rt:
                    yield {"type": "reasoning", "text": _rt}
                for tc in (delta.get("tool_calls") or []):
                    idx = tc.get("index", 0) or 0
                    slot = tool_acc.setdefault(idx, {"id": None, "name": None, "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
        except UserStop:
            raise
        except Exception:
            if cancel and cancel():      # reader died because the watchdog closed the socket
                raise UserStop()
            raise
        finally:
            if _watch_done is not None:
                _watch_done.set()
            r.close()
    _tail = think.flush()                                  # emit any held-back partial-tag tail at stream end
    if _tail and _tail[1]:
        if _tail[0] == "token":
            content_parts.append(_tail[1])
        yield {"type": _tail[0], "text": _tail[1]}
    tool_calls = [{"id": s["id"] or f"call_{i}", "type": "function",
                   "function": {"name": s["name"], "arguments": s["arguments"]}}
                  for i, s in sorted(tool_acc.items()) if s["name"]]
    return {"content": "".join(content_parts), "tool_calls": tool_calls, "finish_reason": finish, "usage": usage}


def _chat_with_retry(base_url, api_key, model, messages, max_tok, reasoning=None, cache=False, provider="", cancel=None):
    last = None
    for attempt in range(1, config.RETRIES + 1):
        if cancel and cancel():          # 2026-08-12: don't even open the next attempt after Stop
            raise UserStop()
        try:
            out = yield from _stream_chat(base_url, api_key, model, messages, max_tok, reasoning, cache, provider, cancel=cancel)
            return out
        except Exception as e:
            last = e
            if not getattr(e, "retryable", True):       # 4xx client/config error (bad model id, unsupported param) -> stop now
                break
            if attempt < config.RETRIES:
                wait = min(6 * attempt, config.RETRY_BACKOFF_CAP)
                yield {"type": "status", "text": f"LLM call failed ({e}); retry {attempt}/{config.RETRIES} in {wait}s"}
                # Cancel-aware backoff (2026-08-12): during a provider rate-limit storm the run
                # lives inside these sleeps, so a blind time.sleep(wait) made Stop wait out the
                # whole retry ladder and then exit via the error path (no paused event, no
                # bundle). Poll the cancel flag each second and unwind through UserStop, which
                # the design loop turns into 'paused' + the shipped bundle.
                deadline = time.time() + wait
                while time.time() < deadline:
                    if cancel and cancel():
                        raise UserStop()
                    time.sleep(min(1.0, max(0.0, deadline - time.time())))
    raise RuntimeError(f"LLM call failed: {last}")


# ---------------- main design loop ----------------
_SEARCH_FILLER = {"strength", "section", "equation", "equations", "design", "flexural", "members",
                  "member", "steel", "provisions", "clause", "nominal", "compute", "calculate", "limit",
                  "state", "check", "value", "values", "requirement", "requirements"}

def _search_anchor(query):
    """Coarse fingerprint of a RAG query so REWORDED variants of the same lookup collapse to one signature.
    Prefer the IS dotted clause id(s) (6.6.1.1, 5.2.1.1, 8.1); else a small set of content words."""
    q = (query or "").lower()
    codes = re.findall(r"\b\d+\.\d+(?:\.\d+)*\b", q)         # IS dotted clause ids
    if not codes:
        codes = [re.sub(r"-\d+$", "", c) for c in re.findall(r"\b[a-k]\d+(?:\.\d+)?(?:-\d+)?\b", q)]
    if codes:
        return frozenset(codes[:3])                      # e.g. 'F2', 'F2-2', 'F2-5' all -> {'f2'}
    toks = [t for t in re.findall(r"[a-z]{4,}", q) if t not in _SEARCH_FILLER]
    return frozenset(sorted(set(toks))[:5])

def _sig(nm, args):
    """Loop-guard signature -- collapses NEAR-duplicate calls (reworded searches, identical re-runs) to one key,
    while letting genuine progress (a DIFFERENT cfg.py write) stay distinct."""
    if nm == "run_python":
        code = re.sub(r"#.*", "", args.get("code", ""))                       # ignore comment-only edits
        return ("run_python", hashlib.md5(" ".join(code.split()).encode()).hexdigest()[:10])
    if nm == "write_file":                                                    # path + content hash: rewriting the
        body = str(args.get("content", ""))                                   # SAME bytes trips; editing does NOT
        return ("write_file", args.get("path", ""), hashlib.md5(body.encode()).hexdigest()[:8])
    if nm == "search_engineering_standards":
        return ("search", args.get("collection", "IS801"), _search_anchor(args.get("query", "")))
    return (nm, json.dumps(args, sort_keys=True)[:120])


def _resume_preamble(ws, building):
    """If a prior cfg.py exists for this building, hand it to the model so a fresh resume continues it."""
    try:
        p = ws.jobs / building / "cfg.py"
        if p.exists():
            src = p.read_text(encoding="utf-8", errors="replace")[:20000]
            return ("RESUME -- a previous design for this building exists. Below is its saved cfg.py: read it, keep "
                    "what is sound, apply any requested change, then re-run pipeline.design_and_report (which rewrites "
                    "design/calc_package_cfs.json).\n\nEXISTING cfg.py:\n```python\n%s\n```\n\n" % src)
    except Exception:
        pass
    return ""


def _archive_report(ws, building):
    """Before a re-design overwrites it, snapshot the current report.html (figures inlined) to
    report_v<N>.html so prior COMPLETED reports remain in the job folder and stay downloadable."""
    try:
        from . import bundle
        jd = ws.jobs / building
        if not (jd / "report.html").exists():
            return
        n = 1 + len(list(jd.glob("report_v*.html")))
        (jd / f"report_v{n}.html").write_text(bundle.selfcontained_html(jd), encoding="utf-8")
    except Exception:
        pass


def _save_conv(path, messages):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / (path.name + ".tmp~")
        tmp.write_text(json.dumps(messages), encoding="utf-8")
        os.replace(tmp, path)                    # ATOMIC: a mid-write kill can never corrupt the resume state
    except Exception:
        pass


def run_design(ws, executor, base_url, api_key, model, building, brief, max_tok=32000, reasoning="high", provider="", resume=False, images=None, cancel=None):
    if model == "MOCK":
        yield from _mock_design(ws, executor, building, brief)
        return
    rparam = _reasoning_param(reasoning, base_url)
    cache_on = any(x in (model or "").lower() for x in ("claude", "anthropic"))   # Anthropic prompt caching via OpenRouter
    ws.building = building
    if resume and brief:                       # re-design (Continue WITH a new instruction) -> keep the prior report
        _archive_report(ws, building)
    conv_path = ws.jobs / building / "conversation.json"
    messages = None
    if resume and conv_path.exists():
        try:
            messages = json.loads(conv_path.read_text(encoding="utf-8"))
            for m in messages:              # heal empty assistant turns saved by older versions (provider 400s)
                c = m.get("content")
                if m.get("role") == "assistant" and (isinstance(c, str) and not c.strip()):
                    m["content"] = None if m.get("tool_calls") else "(empty turn)"
            if brief:                       # a NEW instruction -> continue the SAME design interactively
                messages.append({"role": "user", "content":
                    brief + "\n\n(Apply this change to the existing design: edit jobs/" + building +
                    "/cfg.py, re-run pipeline.design_and_report for fresh demands, re-derive the affected "
                    "IS 801 / IS 800 results into design/calc_package_cfs.json, read STATUS.md and iterate. Keep everything "
                    "else as-is.)"})
                yield {"type": "status", "text": f"continuing '{building}' with your new instruction ({len(messages)} messages in context)"}
            else:                           # empty brief -> plain resume of an interrupted run
                yield {"type": "status", "text": f"resumed '{building}' from saved conversation ({len(messages)} messages)"}
        except Exception:
            messages = None
    if messages is None:
        system = contract.system_prompt(has_images=bool(images))
        sys_content = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}] if cache_on else system
        head = _resume_preamble(ws, building) if resume else ""
        user = head + f"BUILDING NAME: {building}\n\nDESIGN BRIEF:\n{brief}\n\nDesign this building now."
        if re.search(r"podium|\bover\b[^.\n]{0,40}(concrete|steel frame)|two.stage", brief or "", re.I):
            user += ("\n\n[framework note] This brief looks like a PODIUM building. Under D3 there is no two-stage "
                     "analysis: the hot-rolled braced frames run CONTINUOUS from the foundation through the podium "
                     "storeys to the roof as ONE 3-D model (IS 1893 7.x, IS 800 Section 12); the podium storeys carry "
                     "their own heavier loads in geometry / loads and the CFS floors above are gravity members.")
        if re.search(r"portal", brief or "", re.I) and re.search(r"hyderabad", brief or "", re.I):
            user += ("\n\n[framework note] This is the ONE all-CFS portal brief: cfg['all_cfs_portal'] = True, "
                     "cfg['portal']['seismic_basis'] = 'elastic_R1' (R = 1.0 stated), IS 801 working stress, wind governs; "
                     "see tests/fixtures/IN_CFS_Ex5/build_and_run.py for the schema.")
        elif re.search(r"portal|warehouse|cold.?storage", brief or "", re.I):
            user += ("\n\n[framework note] A portal brief outside Hyderabad is a HOT-ROLLED IS 800 SMF portal "
                     "(SMRF R 5.0, h < 15 m) with cold-formed purlins / girts / mezzanine joists to IS 801; declare it "
                     "in cfg['lateral_frame'] with system 'SMF'.")
        if images:                              # vision: attach reference image(s) as OpenAI image_url parts
            user_content = [{"type": "text", "text": user}]
            for im in images:
                url = (im or {}).get("data_url")
                if url:
                    user_content.append({"type": "image_url", "image_url": {"url": url}})
            yield {"type": "status", "text": f"attached {len(user_content) - 1} reference image(s) to the brief"}
        else:
            user_content = user
        messages = [{"role": "system", "content": sys_content}, {"role": "user", "content": user_content}]
        yield {"type": "status", "text": f"model={model} | contract={len(system)} chars | sandbox={executor.name}"}
    stuck = 0
    sig_counts = {}
    fired_hints = set()              # hardening #7: one-shot phase hints keyed by trigger id
    nudged_sigs = set()              # signatures already soft-nudged (REPEAT_NUDGE)
    seen_paths = set()               # write_file paths seen so far (a progress signal)
    no_progress = 0                  # consecutive steps with no new file, no rc=0 run, no search
    stall_nudged = False
    cum_in = cum_out = 0
    searches = 0
    nudged = False
    run_start = time.time()
    for step in range(1, config.MAX_STEPS + 1):
        if cancel and cancel():                       # user pressed Stop -> halt cleanly, keep context for Continue
            _save_conv(conv_path, messages)
            yield {"type": "paused", "reason": "stopped by user",
                   "detail": "Progress is saved -- type a change (optional) and click Continue to resume; "
                             "Download has your results so far."}
            return
        if config.RUN_SOFT_DEADLINE_SEC and time.time() - run_start > config.RUN_SOFT_DEADLINE_SEC:
            _save_conv(conv_path, messages)            # pause+save before the platform's per-run cap (e.g. Cloud Run 60 min)
            yield {"type": "paused", "reason": "approaching the platform's per-run time limit",
                   "detail": "Your progress was saved automatically. Click Continue to resume -- the time limit resets, so it "
                             "picks up where it left off. You can also download any results so far."}
            return
        if config.MAX_CALLS and step > config.MAX_CALLS:
            yield {"type": "error", "text": f"call budget reached ({config.MAX_CALLS} model calls) -- run aborted"}
            return
        _prune_rag(messages, config.RAG_KEEP_RECENT)
        _save_conv(conv_path, messages)
        if searches >= config.RAG_SEARCH_SOFTCAP and not nudged:
            nudged = True
            messages.append({"role": "user", "content":
                "You have gathered ample IS 801/811/875/1893 references -- STOP searching now: write cfg.py with every "
                "retrieval hit cited in cfg['load_plan']['retrieval'] and run pipeline.design_and_report(name, cfg); "
                "the pipeline computes every capacity from the cited clauses. Re-search only ONE specific clause if it "
                "is genuinely missing."})
        try:
            try:
                out = yield from _chat_with_retry(base_url, api_key, model, messages, max_tok, rparam,
                                                  cache_on, provider, cancel=cancel)
            except UserStop:
                _save_conv(conv_path, messages)
                yield {"type": "paused", "reason": "stopped by user",
                       "detail": "Halted mid-generation -- progress is saved; click Continue to resume."}
                return
            except GeneratorExit:                      # client gone mid-generation: save silently, no yields allowed
                _save_conv(conv_path, messages)
                raise
        except Exception as e:
            yield {"type": "error", "text": str(e)}
            return
        u = out.get("usage") or {}
        li, lo = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
        if li or lo:
            cum_in += li; cum_out += lo
            yield {"type": "usage", "last_in": li, "last_out": lo, "cum_in": cum_in, "cum_out": cum_out}
        # Some providers (e.g. Moonshot/Kimi) reject assistant messages whose content is an EMPTY
        # string ("must not be empty"). OpenAI's own API emits null content on tool-call turns, so
        # mirror that; an empty turn with no tool calls gets a placeholder (it stays in history
        # when the nudge below pushes past it).
        _c = out["content"]
        assistant = {"role": "assistant",
                     "content": _c if (_c or "").strip() else (None if out["tool_calls"] else "(empty turn)")}
        if out["tool_calls"]:
            assistant["tool_calls"] = out["tool_calls"]
        messages.append(assistant)
        truncated = out["finish_reason"] == "length"
        final_text = (out["content"] or "").strip()
        if not out["tool_calls"]:
            if (truncated or not final_text) and stuck < 5:     # cut off OR an EMPTY turn -- never mistake it for 'done'
                stuck += 1
                why = "cut off at the token limit" if truncated else "empty (no text and no tool call)"
                yield {"type": "status", "text": f"turn {why}; nudging to continue ({stuck}/5)"}
                messages.append({"role": "user", "content":
                    "Your previous turn was " + ("cut off before making a tool call. Use LESS reasoning" if truncated
                    else "EMPTY -- you produced no text and no tool call") + ". Do NOT stop here -- the design is not "
                    "finished. CONTINUE with your NEXT tool call (write cfg.py, run pipeline.design_and_report, derive "
                    "IS 801 capacities/schedules into calc_package.json, run consistency.check, build the report). Give a final "
                    "written answer ONLY if the design is genuinely complete (report built, consistency.check passes)."})
                continue
            if not final_text:                                  # exhausted nudges, still empty -> pause, never fake 'done'
                _save_conv(conv_path, messages)
                yield {"type": "paused", "reason": "the model returned an empty turn and stopped producing output",
                       "detail": "The run did not finish (no report yet). Click Continue to resume it; if it keeps "
                                 "stalling, raise max tokens or try a different model."}
                return
            _gate_probs = _completion_gate(ws)
            _gate_forced = getattr(ws, "_gate_forced", 0)
            if _gate_probs and _gate_forced < 2:
                ws._gate_forced = _gate_forced + 1
                ws.log("completion_gate", "final answer refused", "%d problem(s)" % len(_gate_probs))
                yield {"type": "milestone", "text": "completion gate: %d problem(s) -- run continues"
                       % len(_gate_probs)}
                messages.append({"role": "user", "content":
                    "COMPLETION GATE (enforced): the design is NOT done -- calc_package.json has "
                    "unresolved problems:\n- " + "\n- ".join(_gate_probs) +
                    "\nFix each one (resize the member and re-run the pipeline, design the missing "
                    "connection/collector, or add {'waived': '<engineering justification>'} to the entry "
                    "if it genuinely does not apply), re-run consistency.check, then finish."})
                continue
            if _gate_probs:
                final_text += ("\n\n[completion gate] NOTE: finishing with %d unresolved package "
                               "problem(s) after 2 forced continuations:\n- " % len(_gate_probs)
                               + "\n- ".join(_gate_probs))
            yield {"type": "assistant", "text": final_text}
            _evict_all_rag(messages)                  # design complete -> drop raw spec-RAG chunks to file pointers before saving
            _save_conv(conv_path, messages)
            yield {"type": "done", "building": ws.building}
            return
        stuck = 0
        pending_nudges = []           # user-message nudges injected AFTER the batch (keeps every tool_call valid)
        progressed = False
        pause = None                  # (name, count) when the loop guard pauses this step
        rag_halt = None               # set when a RAG query found the RAG API unavailable -> halt + Continue
        tcs = out["tool_calls"]
        for idx, tc in enumerate(tcs):
            nm = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except Exception:
                args = {}
            sig = _sig(nm, args); sig_counts[sig] = sig_counts.get(sig, 0) + 1; n = sig_counts[sig]
            if n >= config.REPEAT_LIMIT:                       # PAUSE -- but keep the conversation valid for Continue
                pause = (nm, n)
                for rest in tcs[idx:]:                         # synthetic results so no tool_call is left dangling
                    messages.append({"role": "tool", "tool_call_id": rest["id"], "name": rest["function"]["name"],
                        "content": json.dumps({"blocked": f"loop guard paused the run: '{nm}' repeated {n}x with no "
                            "progress. Fix the ONE failing thing, then continue -- do not repeat the same call."})})
                break
            if n == config.REPEAT_NUDGE and sig not in nudged_sigs:    # soft nudge ONCE before the hard pause
                nudged_sigs.add(sig)
                pending_nudges.append(f"You have called {nm} {n} times with no new result. STOP repeating it -- read the "
                    "last result/error and change approach: fix the SPECIFIC problem, or move on to the next step.")
            yield {"type": "tool", "step": step, "name": nm, "title": _tool_title(nm, args),
                   "code": ((args.get("code", "") or "")[:200] if nm == "run_python" else "")}
            _t0 = time.time()
            try:
                result = dispatch(nm, args, ws, executor)
            except Exception as _de:             # a tool crash must NEVER kill the run (this lost user data)
                try:
                    ws.log(nm, "tool crashed", f"{type(_de).__name__}: {_de}"[:180])
                except Exception:
                    pass
                result = {"error": f"tool '{nm}' crashed: {type(_de).__name__}: {_de}",
                          "hint": "the run continues -- fix the arguments (e.g. give write_file a real FILE "
                                  "path like 'cfg.py', never a folder) and retry"}
            _ms = int((time.time() - _t0) * 1000)
            if nm == "search_engineering_standards":
                searches += 1; progressed = True
                if "opensees" in str(args.get("collection", "")).lower():
                    ws._os_docs_since_err = True        # R21 gate cleared by an OpenSees docs query
            elif nm == "write_file":
                pth = args.get("path", "")
                if pth and pth not in seen_paths: seen_paths.add(pth); progressed = True
            elif nm == "run_python" and isinstance(result, dict) and result.get("returncode") == 0:
                progressed = True
            yield {"type": "tool_result", "step": step, "name": nm, "summary": _result_preview(nm, result), "ms": _ms}
            _rtxt = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            for _hid, _hre, _hmsg in _PHASE_HINTS:
                if _hid not in fired_hints and _hre.search(_rtxt or ""):
                    fired_hints.add(_hid)
                    pending_nudges.append("[phase hint] " + _hmsg)
                    break
            for _mk in _milestones(nm, args, result):
                yield {"type": "milestone", "text": _mk}
            _payload = json.dumps(result)
            _cap = config.RAG_OUT_CAP if (isinstance(result, dict) and result.get("saved")) else config.TOOL_OUT_CAP
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": nm,
                             "content": _payload[:_cap]})
            if nm == "search_engineering_standards" and isinstance(result, dict) and result.get("rag_unavailable"):
                rag_halt = result.get("message", "cannot access the RAG API, restart the RAG server then click Continue.")
                for rest in tcs[idx+1:]:           # synthetic results so no tool_call is left dangling for Continue
                    messages.append({"role": "tool", "tool_call_id": rest["id"], "name": rest["function"]["name"],
                                     "content": json.dumps({"blocked": "run halted: RAG API unavailable"})})
                break
        if rag_halt is not None:                   # RAG is MANDATORY -> stop and let the user restart it, then Continue
            _save_conv(conv_path, messages)
            yield {"type": "paused", "reason": rag_halt,
                   "detail": "Grounding requires the engineering-standards RAG, which is not reachable. Restart the RAG "
                             "server, then click Continue to resume this design from where it stopped."}
            return
        if pause is not None:
            _save_conv(conv_path, messages)
            yield {"type": "paused", "reason": f"'{pause[0]}' repeated {pause[1]}x with no progress",
                   "detail": "This is typically a symptom of less intelligent LLMs. Check what the agent spun its "
                             "wheels on -- you may be able to provide some advice in the input box. Otherwise, just "
                             "hit Continue and see if it self-fixes."}
            return
        if progressed:                                         # progress tracker: stall = no file/run/search advancing
            no_progress = 0; stall_nudged = False
        else:
            no_progress += 1
            if no_progress >= config.PROGRESS_STALL_PAUSE:
                _save_conv(conv_path, messages)
                yield {"type": "paused", "reason": f"{no_progress} steps with no forward progress",
                       "detail": "No new file written and no successful run recently -- the run looks stuck. Review the log, "
                                 "then click Continue with a specific instruction or fix."}
                return
            if no_progress >= config.PROGRESS_STALL_NUDGE and not stall_nudged:
                stall_nudged = True
                pending_nudges.append(f"You have gone {no_progress} steps with no progress (no new file, no successful run). "
                    "Step back: name the ONE thing blocking you and fix exactly that -- or write up what you already have.")
        for msg in pending_nudges:                             # inject AFTER the batch so every tool_call has its result
            messages.append({"role": "user", "content": msg})
    yield {"type": "error", "text": "max steps reached without a final answer"}


_PIPE_KEYS = ("model_valid", "model_complete", "demand", "figure", "consisten", "pass", "fail", "flag",
              "warning", "exported", "report", "next step", "mode ", "period", "complete", "error")

def _code_label(code):
    c = code or ""
    if "design_and_report" in c: return "run design pipeline (model + demands + figures + report)"
    if "build_and_preview" in c: return "build preview model + figures"
    if "build_report" in c: return "render report"
    if "consistency" in c: return "consistency check"
    if "design_pipeline" in c or "import pipeline" in c: return "design pipeline"
    if "openseespy" in c or "ops." in c: return "OpenSees / Python"
    return "Python"

def _tool_title(name, args):
    a = args or {}
    if name == "run_python":
        return f"run_python · {_code_label(a.get('code',''))}"
    if name == "search_engineering_standards":
        coll = (a.get("doc") or a.get("collection") or "engineering_standards_IS801").replace("engineering_standards_", "")
        flt = "".join(f" [{k}={a[k]}]" for k in ("clause", "chapter") if a.get(k))
        if a.get("type"):                                   # the policy form: `exact_equation G5-1`
            return f"search {coll} {a['type']} ‹{(a.get('query') or '')[:64]}›{flt}"
        return f"search {coll} ‹{(a.get('query') or '')[:64]}›{flt}"
    if name == "write_file":   return f"write_file {a.get('path','')}"
    if name == "read_file":    return f"read_file {a.get('path','')}"
    if name == "new_activity_log": return f"new_activity_log {a.get('building','')}"
    if name == "list_files":   return f"list_files {a.get('path','.')}"
    return name

def _pick_lines(text, n=8):
    lines = [l.rstrip() for l in (text or "").splitlines() if l.strip()]
    picked = [l for l in lines if any(k in l.lower() for k in _PIPE_KEYS)]
    body = (picked or lines)[-n:]
    return [l[:160] for l in body]

def _result_preview(name, result):
    if not isinstance(result, dict):
        return str(result)[:200]
    if "returncode" in result:                                   # run_python (success or failure)
        rc = result.get("returncode")
        se, so = result.get("stderr", "") or "", result.get("stdout", "") or ""
        if rc not in (0, None) or result.get("timed_out") or "Traceback (most recent" in se:
            # keep the LOG clean: show only pass/fail. The agent still receives the FULL traceback in its tool
            # result (and it is kept in conversation.json), so it self-corrects in the background -- the multi-line
            # traceback is just noise in the activity log.
            return "TIMEOUT" if result.get("timed_out") else f"rc={rc} ✗"
        body = _pick_lines(so)
        return "rc=0 ✓" + ("\n" + "\n".join(body) if body else "")
    if "error" in result:
        return "error: " + str(result["error"])[:240]
    if name == "search_engineering_standards":
        if result.get("disabled"): return "RAG disabled — using cited IS 801/811 knowledge"
        res = result.get("results") if isinstance(result.get("results"), list) else None
        bits = [f"{len(res) if res is not None else 0} hits"]
        if result.get("policy"):                             # what actually went to the QFM
            bits.append("sent as " + str(result["policy"])[:120])
        cl = result.get("clauses_found") or []
        if cl: bits.append("clauses " + ", ".join(cl[:6]))
        if result.get("saved"): bits.append("saved " + result["saved"])
        return " · ".join(bits)
    if result.get("ok"):
        return "ok " + str(result.get("path", result.get("building", "")))[:120]
    if "counts_by_tool" in result:                       # activity_summary -- its 'entries' are record dicts, not strings
        cb = result.get("counts_by_tool") or {}
        return f"{result.get('total_calls', 0)} tool calls — " + ", ".join(f"{k}×{v}" for k, v in cb.items())
    if "entries" in result:                              # list_files -- filenames
        return f"{len(result['entries'])} entries: " + ", ".join(str(e) for e in result["entries"][:12])[:160]
    if "total_lines" in result:
        return "read " + str(result.get("shown_lines", ""))
    return json.dumps(result)[:200]

def _milestones(name, args, result):
    out = []
    if not isinstance(result, dict):
        return out
    if name == "write_file":
        p = (args.get("path") or "").lower()
        if p.endswith("cfg.py"): out.append("cfg.py saved")
        elif p.endswith("calc_package_cfs.json"): out.append("WARNING: calc_package_cfs.json written by hand -- the gate re-derives the status")
    if name == "run_python" and result.get("returncode") == 0:
        c = args.get("code", "")
        if "design_and_report" in c: out.append("Model analysed — demands + figures + report generated")
        elif "build_and_preview" in c: out.append("Preview model built")
        elif "build_report" in c: out.append("Report re-rendered")
        if "consistency" in c: out.append("Consistency check run")
    return out


# ---------------- MOCK design (offline pipe test) ----------------
def _mock_design(ws, executor, building, brief):
    """Scripted run to exercise the sandbox pipe (no LLM): imports the India engines and computes one IS 801 hand value
    (the CLR100X50X15X2 stud of the Ex1 reference building) -- no wall path, no portal LRFD combos (D3)."""
    yield {"type": "status", "text": "MOCK model -- scripted run to exercise the sandbox pipe (no LLM)"}
    seq = [
        ("new_activity_log", {"building": building}),
        ("write_file", {"path": f"jobs/{building}/cfg.py",
                        "content": "# MOCK India CFS cfg (metres / kN/m2) -- see contract/AGENT_START.md for the full schema\n"
                                   "cfg = dict(name='MOCK', jurisdiction='india', units='m', design_basis='IS801_WSM')\n"}),
        ("run_python", {"code":
            "import india_cfs_env, is811_sections as S, is801_members as M, india_cfs_basis as B\n"
            "sec = S.props('CLR100X50X15X2')\n"
            "print('IS 811 catalogue OK:', len(S.list_labels()), 'sections;', sec['label'], 'A =', sec['A'], 'mm2')\n"
            "r = M.compression_allowable(sec, 240.0, 3000.0, 300.0, 300.0, braced_against_twist=True)\n"
            "print('IS 801 6.6.1.1 Fa1 = %.1f MPa (Q = %.3f)' % (r['Fa1_MPa'], r['Q']))\n"
            "rows = B.cfs_combinations({'cfs_combinations': 'auto', 'story_forces': {'W_X': {'1': [1, 0, 0]}, 'EQ_X': {'1': [1, 0, 0]}}})\n"
            "print('IS 875-5 8.1 combinations:', len(rows), 'rows; WL/EL increase', [x['allowable_increase'] for x in rows if x['fW']][:1])\n"
            "open('mock_marker.txt', 'w').write('sandbox ran the India CFS engine')\n"}),
    ]
    for i, (nm, args) in enumerate(seq, 1):
        yield {"type": "tool", "step": i, "name": nm, "title": _tool_title(nm, args)}
        result = dispatch(nm, args, ws, executor)
        yield {"type": "tool_result", "step": i, "name": nm, "summary": _result_preview(nm, result)}
        if nm == "run_python" and isinstance(result, dict) and result.get("returncode") not in (0, None):
            yield {"type": "error", "text": "sandbox run_python failed: " + _result_preview(nm, result)}
            return
    yield {"type": "assistant", "text":
           f"MOCK run complete for '{building}'. The sandbox imported the India CFS engine (IS 811 catalogue, IS 801 "
           f"member checks, IS 875-5 combinations) and wrote artifacts into jobs/{building}/. Wire a real LLM (set its "
           f"base-url + key in Settings) to produce an actual design. What would you like next?"}
    yield {"type": "done", "building": ws.building}
