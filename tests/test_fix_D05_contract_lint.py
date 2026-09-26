"""D05 contract lint (CFS): every cfg key the CFS-only modules read is named somewhere in contract/*.md or README*.md.

Scanned: steel_engine/*.py of this repo (the CFS-only modules and hr_vendor_runner.py; the vendored HR engine in
steel_engine/hr_vendor/ is linted in the HR repo).  Two kinds of reads:
  * top-level keys -- cfg.get("key"), cfg.setdefault("key"), cfg["key"], (cfg or {}).get("key");
  * the documented CFS sub-blocks read through their conventional local names -- lf (cfg['lateral_frame']), site,
    geo (cfg['geometry']), ld (cfg['loads']), occ (cfg['occupancy']), cm (cfg['cfs_members']), portal.

Allowlist (documented here, deliberately minimal): keys with a leading underscore -- engine-private caches written
by the engine itself (e.g. the portal's _W / _secs).  Fix a failure by documenting the key, not by widening it."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "steel_engine"

TOP_RE = re.compile(r"""(?:\bcfg|(?<!\w)\(cfg or \{\}\))(?:\.get\(|\.setdefault\(|\[)\s*(['"])([A-Za-z_][A-Za-z0-9_]*)\1\s*[,)\]]""")
SUB_RE = re.compile(r"""(?<![\w.])(?:lf|site|geo|ld|occ|cm|portal)(?:\.get\(|\[)\s*(['"])([A-Za-z_][A-Za-z0-9_]*)\1\s*[,)\]]""")


def is_allowlisted(key):
    return key.startswith("_")


def engine_keys(rx):
    keys = {}
    for f in sorted(ENGINE.glob("*.py")):                   # top level only: hr_vendor/ is not scanned here
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in rx.finditer(line):
                keys.setdefault(m.group(2), []).append("%s:%d" % (f.name, i))
    return keys


def docs_text():
    parts = [p.read_text(encoding="utf-8") for p in sorted((ROOT / "contract").glob("*.md"))]
    parts += [p.read_text(encoding="utf-8") for p in sorted(ROOT.glob("README*.md"))]
    return "\n".join(parts)


def _named(key, text):
    return re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(key), text) is not None


def test_scanner_is_not_vacuous():
    top, sub = engine_keys(TOP_RE), engine_keys(SUB_RE)
    assert len(top) > 20 and len(sub) > 50, (len(top), len(sub))
    for k in ("lateral_frame", "cfs_members", "all_cfs_portal", "load_plan"):
        assert k in top, k
    for k in ("diaphragm_stiffness", "flexible_diaphragm_eor", "gold", "custom_build_module", "hr_cfg_extra",
              "wind_structure_class", "partition_seismic_kNm2"):
        assert k in sub, k


def test_every_cfs_cfg_key_is_documented():
    text = docs_text()
    missing = {}
    for rx in (TOP_RE, SUB_RE):
        for k, v in sorted(engine_keys(rx).items()):
            if not is_allowlisted(k) and not _named(k, text):
                missing[k] = v[:3]
    assert not missing, "cfg keys read by the CFS modules but named in no contract/*.md or README*.md: %s" % missing


def test_allowlist_is_only_private_keys():
    allow = sorted({k for rx in (TOP_RE, SUB_RE) for k in engine_keys(rx) if is_allowlisted(k)})
    assert all(k.startswith("_") for k in allow)
    assert len(allow) <= 5, allow


def test_phase2_passthrough_keys_in_agent_start():
    """D04 extension: the phase-2 keys that reach the HR run from a CFS job are in the CFS AGENT_START."""
    agent = (ROOT / "contract" / "AGENT_START.md").read_text(encoding="utf-8")
    for k in ("diaphragm_stiffness", "flexible_diaphragm_analysis", "flexible_diaphragm_eor", "roof_planes",
              "roof_regions", "eave_coords_m", "hr_vendor/frame_build.py", "RAG_API_URL", "INDIA_CORPUS_ROOT",
              "not_tabulated", "server_error", "rag_dir"):
        assert k in agent, k
