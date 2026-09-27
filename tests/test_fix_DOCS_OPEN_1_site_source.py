"""DOCS-OPEN-1: the CFS lateral sub-run forwards site.Vb_source with the site lat / long and the ruling R5 site-proxy
record (proxy_town, distance_km, basis, verify, annex_found / corpus_status), and site.zone_source with its record, so
'derived_from_map' and 'site_proxy' pass the HR preflight when properly recorded (and are still refused when not)."""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_env  # noqa: E402,F401
import india_cfs_lateral as L  # noqa: E402
import india_wind_tables as WT  # noqa: E402  (vendored HR)


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


def _hr_errors(spec):
    """The HR preflight wind / zone rules on the sub-run's load plan (as hr_vendor_runner passes it)."""
    f = WT.wind_findings({"load_plan": spec["load_plan"], "city": "Noida"})
    return [m for s, m in f if s == "ERROR" and ("Vb" in m or "zone" in m or "proxy" in m)], f


def test_derived_from_map_with_lat_long_passes():
    cfg = _cfg()
    cfg["site"].update(Vb_source="derived_from_map", lat=28.54, long=77.39, zone_source="derived_from_map")
    spec = L.build_hr_spec(cfg, "t")
    ws, ss = spec["load_plan"]["wind_summary"], spec["load_plan"]["seismic_summary"]
    assert ws["Vb_source"] == "derived_from_map" and ws["lat"] == 28.54 and ws["long"] == 77.39
    assert ss["zone_source"] == "derived_from_map" and ss["lat"] == 28.54
    errs, _ = _hr_errors(spec)
    assert errs == []
    # without lat / long the HR preflight still refuses it
    c2 = copy.deepcopy(cfg)
    for k in ("lat", "long"):
        c2["site"].pop(k)
    errs, _ = _hr_errors(L.build_hr_spec(c2, "t"))
    assert any("derived_from_map needs the site lat/long" in m for m in errs)


def test_site_proxy_record_passes_as_warn():
    cfg = _cfg()
    rec = {"proxy_town": "Delhi", "distance_km": 20.0, "basis": "IS 875-3 Annex A Delhi 47 m/s; Noida not tabulated",
           "verify": True, "annex_found": False}
    cfg["site"].update(Vb_source="site_proxy", zone_source="site_proxy", site_proxy=rec)
    spec = L.build_hr_spec(cfg, "t")
    ws, ss = spec["load_plan"]["wind_summary"], spec["load_plan"]["seismic_summary"]
    for k, v in rec.items():
        assert ws[k] == v and ss[k] == v
    errs, f = _hr_errors(spec)
    assert errs == []
    warns = [m for s, m in f if s == "WARN" and "site_proxy" in m]
    assert any(m.startswith("Vb from site_proxy 'Delhi'") for m in warns)
    assert any(m.startswith("zone from site_proxy 'Delhi'") for m in warns)
    # an incomplete record is refused (no verify, no not-tabulated statement)
    c2 = copy.deepcopy(cfg)
    c2["site"]["site_proxy"] = {"proxy_town": "Delhi", "distance_km": 20.0, "basis": "x"}
    errs, _ = _hr_errors(L.build_hr_spec(c2, "t"))
    assert any("Vb_source = 'site_proxy' refused" in m for m in errs)
    assert any("zone_source = 'site_proxy' refused" in m for m in errs)


def test_quantity_specific_record_and_plain_annex_unchanged():
    cfg = _cfg()
    cfg["site"].update(Vb_source="site_proxy",
                       Vb_site_proxy={"proxy_town": "Delhi", "distance_km": 20.0, "cite": "Annex A Delhi",
                                      "verify": True, "corpus_status": "not_tabulated"})
    ws = L.build_hr_spec(cfg, "t")["load_plan"]["wind_summary"]
    assert ws["basis"] == "Annex A Delhi" and ws["corpus_status"] == "not_tabulated"
    assert "zone_source" not in L.build_hr_spec(cfg, "t")["load_plan"]["seismic_summary"]
    ws0 = L.build_hr_spec(_cfg(), "t")["load_plan"]["wind_summary"]
    assert ws0["Vb_source"].startswith("IS 875-3 Annex A") and "proxy_town" not in ws0 and "lat" not in ws0
