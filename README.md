# Steltic India CFS

A free, open-source **India (IS/BIS) cold-formed steel design agent** that runs locally.
Paste a design brief and watch the agent build an OpenSees model + a stamped-style HTML report +
an interactive 3D viewer — **bringing your own LLM** (API base-url + key, held in memory only).

This repository is the **India CFS variant** of [Steltic/steltic_cfs](https://github.com/Steltic/steltic_cfs)
(USA AISI/ASCE). Do **not** confuse the two. Design authority: **IS 801:1975** + **IS 811:1987**
(+ Amd1 when relevant). Loads: **IS 875 Parts 1–5** and **IS 1893 Part 1:2016**, retrieved LIVE
via RAG every job (not hardcoded in the engine).

```
browser ──▶ FastAPI app (localhost) ──▶ your LLM (key in app memory, never stored)
                 │  parses tool calls
                 ▼
           sandbox executor (run_python only) — Docker when available
                 │
           steel engine + OpenSees ─▶ report.html + viewer_3d.html
```

> **Not for construction.** Every output is produced by your own AI model, may be incomplete or
> incorrect, and must be independently checked and sealed by a licensed professional engineer before
> any use for design, construction, or permitting. See [DISCLAIMER.md](DISCLAIMER.md).

## For videos and demonstrations see [stelticai.com](https://stelticai.com)

## Install & run

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install --python 3.12 steltic-cfs-india
steltic-cfs-india                 # starts on http://127.0.0.1:8000 and opens your browser
```

Or from a checkout:

```bash
git clone https://github.com/Steltic/steltic_CFS_india && cd steltic_CFS_india
python -m venv .venv && . .venv/bin/activate
pip install -e .
./run_local.sh               # http://localhost:8000
```

First run: open **Settings**, enter your provider's **API base URL**, **API key**, and **model**.
Point `RAG_API_URL` at a server indexed with the **India** corpus (`/workspace/engineering_rag_india`
on the builder box — never the USA `/workspace/engineering_rag`). Then paste a brief and click
**Design building**.

Offline smoke test: set Model to `MOCK`.

## Critical difference from USA steltic_cfs: loads are retrieved

| | USA `steltic_cfs` | India `steltic_CFS_india` |
|--|--|--|
| Design code | AISI S100 / S240 / S400 | IS 801:1975 + IS 811:1987 (+Amd1) |
| Loads | ASCE 7-22 **computed inside the engine** | IS 875 + IS 1893 **RAG every job → cfg['load_plan']** |
| Corpus | `/workspace/engineering_rag` | `/workspace/engineering_rag_india` |

The agent must call `search_engineering_standards` against `engineering_standards_IS875_P*` and
`engineering_standards_IS1893` before `pipeline.design_and_report`, then write retrieved factors into
`cfg['load_plan']` (schema in `steel_engine/india_loads.py`). Preflight fails closed if that is missing.
`cfs_pipeline.wind_story_forces()` and `engine3d.wind_forces()` raise on this branch.

## Sandbox

Same as USA: `EXECUTOR=auto|docker|subprocess`. Binds to 127.0.0.1; no auth — don't expose the port.

## Engineering-standards RAG (required for India)

Ground the agent with the India QFM corpus (IS 801, IS 811, IS 875 Parts 1–5, IS 1893 Part 1, …).

```bash
cd /workspace/engineering_rag_india
PYTHONPATH=scripts .venv/bin/python scripts/search.py exact_section 5.2.1 --doc IS_801_1975 --limit 2
```

Set `RAG_API_URL` / `RAG_API_TOKEN` / optionally `RAG_ALIASES_FILE` to the India aliases file.

## License

MIT — see [LICENSE](LICENSE), [NOTICE](NOTICE) and [DISCLAIMER.md](DISCLAIMER.md).
