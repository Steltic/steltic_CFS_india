"""
pipeline.py  --  the design entry point the agent runs on an India CFS job (decisions D3 / D5).

    import pipeline
    res = pipeline.design_and_report(name, cfg)     # preflight -> hot-rolled lateral frame (vendored HR India pipeline,
                                                    # subprocess) -> IS 801 cold-formed members -> diaphragm -> package,
                                                    # report.html, viewer_3d.html, consistency, design status, STATUS.md
    print(res)                                      # {status, n_reasons, reasons, report_html, root, lateral_status}

cfg schema: see india_cfs_lateral (site / occupancy / geometry / loads / lateral_frame / cfs_members / load_plan) and
india_cfs_portal (all-CFS elastic portal, cfg['all_cfs_portal'] = True, cfg['portal']).  Metres and kN/m2 in the cfg;
the engines run in N-mm.  Every job needs an explicit cfg['units'] = 'm' and cfg['jurisdiction'] = 'india'.

The sheathed-shear-wall / strap / SBMF / SFIA / ASCE-shaped US paths were removed as a design basis (D3): their code is
kept for reference in steel_engine/usa_reference/ and is NOT importable from here.  A cfg carrying lines_x / span_ft /
wall_vn_* keys is refused by preflight.
"""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import india_cfs_env  # noqa: E402,F401


def _root(name):
    base = os.environ.get("STEEL_BUILDER_JOBS") or _REPO
    return os.path.join(base, name)


def build_and_preview(name, cfg=None):
    """No preview hold on India CFS jobs: the frame layout is declared in cfg['lateral_frame'] / cfg['portal'] and
    reported; call design_and_report directly."""
    return {"name": name, "NOTE": "India CFS path: no separate preview -- call pipeline.design_and_report(name, cfg); "
                                  "state the frame layout, bases and joints in cfg['lateral_frame'] (or cfg['portal'])."}


def design_and_report(name, cfg=None, do_report=True):
    if not isinstance(cfg, dict):
        raise SystemExit("cfg dict required")
    if any(k in cfg for k in ("lines_x", "lines_y", "span_ft", "wall_vn_plf_asd", "strap_Tn_N")):
        raise SystemExit("this cfg uses the removed US wall / kip-in portal schema (D3). Write the India cfg "
                         "(cfg['lateral_frame'] hot-rolled IS 800 frame + cfg['cfs_members'] IS 801 members, metres / kN/m2) "
                         "-- see contract/AGENT_START.md")
    import india_cfs_pipeline as CP
    out = CP.design_and_report(name, cfg, outdir=_root(name), do_report=do_report)
    out["NEXT_STEP"] = ("The run ends with india_cfs_gates.design_status = %s. If it is not 'complete', every open reason is "
                        "listed in STATUS.md and the report: resize the member / connection it names (IS 811 next size, "
                        "is811_sections.next_size), declare the missing EOR input with its cite, or re-proportion the hot-rolled "
                        "frame, then run pipeline.design_and_report again. Never edit calc_package_cfs.json by hand." % out.get("status"))
    return out


if __name__ == "__main__":
    print(__doc__)
