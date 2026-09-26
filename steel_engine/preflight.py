"""preflight.py (CFS India) -- schema-aware checks BEFORE any analysis of an India CFS job (spec WP3.6, CFSREPO-10).

check(cfg) -> [(sev, msg)]; render(res) -> text.  ERRORs block india_cfs_pipeline.design_and_report.
Schema: the D3 CFS cfg (site / occupancy / geometry / loads / lateral_frame | portal / cfs_members / load_plan) --
metres and kN/m2 in the cfg, N-mm in the engines.  No SDS / SD1 / Cd / Om0 anywhere: IS 1893 uses Z, I, R, soil,
Sa/g, Ah.  The hot-rolled frame's own preflight (vendored HR india_checks) runs inside the lateral subprocess.
"""
from __future__ import annotations

import india_cfs_env  # noqa: F401
import india_cfs_gates as G
import india_seismic as IS

INDIA_UNITS_OK = ("m", "metric", "si", "mm", "n-mm")
ZONE_Z = {"II": 0.10, "III": 0.16, "IV": 0.24, "V": 0.36}


def _is_india(cfg):
    j = str((cfg or {}).get("jurisdiction") or "").lower()
    lp = (cfg or {}).get("load_plan") if isinstance((cfg or {}).get("load_plan"), dict) else {}
    return j in ("india", "in", "bis", "is") or str(lp.get("jurisdiction") or "").lower() == "india"


def check(cfg) -> list:
    out = []
    say = lambda s, m: out.append((s, m))
    if not isinstance(cfg, dict):
        return [("ERROR", "cfg is not a dict")]
    if not _is_india(cfg):
        say("ERROR", "this branch designs India jobs only (cfg['jurisdiction'] = 'india'); the US wall / portal path lives "
                     "in steel_engine/usa_reference and is not loaded")
        return out
    if str(cfg.get("units") or "").lower() not in INDIA_UNITS_OK:
        say("ERROR", "cfg['units'] must be explicit ('m': geometry in metres, loads in kN/m2); got %r (WP1.12)" % cfg.get("units"))
    for k in ("SDS", "SD1", "Cd", "Om0", "Ie", "S1"):
        if k in (cfg.get("seis") or {}) or k in cfg:
            say("ERROR", "cfg carries the ASCE key %r -- IS 1893 inputs are Z / zone / I / R / soil / Sa_g / Ah (WP1.13)" % k)
    if any(k in cfg for k in ("lines_x", "lines_y", "wall_vn_plf_asd", "strap_Tn_N", "sfrs_standard")):
        say("ERROR", "sheathed shear walls / straps / SBMF are not a design basis on this branch (D3): the lateral system "
                     "is a hot-rolled IS 800 Section 12 frame (cfg['lateral_frame']) -- see contract/usa_reference for the US material")
    site = cfg.get("site") or {}
    for k in ("city", "zone", "Z", "soil", "Vb", "terrain_category", "cyclone_belt"):
        if site.get(k) is None:
            say("ERROR", "site.%s required" % k)
    if site.get("zone") in ZONE_Z and site.get("Z") is not None and abs(float(site["Z"]) - ZONE_Z[site["zone"]]) > 1e-9:
        say("ERROR", "site.Z %s disagrees with Zone %s (IS 1893 Table 3: %s)" % (site["Z"], site["zone"], ZONE_Z[site["zone"]]))
    if site.get("cyclone_belt") is not None and not site.get("cyclone_belt_cite"):
        say("ERROR", "site.cyclone_belt_cite required (D10: state why the site is in / out of the 60 km belt)")
    if site.get("cyclone_belt") and abs(float(site.get("Kd", 1.0)) - 1.0) > 1e-9:
        say("ERROR", "cyclone belt: Kd shall be 1.0 (IS 875-3 7.2.1)")
    if not site.get("k2_table"):
        say("ERROR", "site.k2_table (IS 875-3 Table 2 for the terrain category, retrieved) required")
    geo = cfg.get("geometry") or {}
    H = geo.get("heights_m") or []
    if not H:
        say("ERROR", "geometry.heights_m required")
    elif any(float(h) > 30.0 or float(h) < 2.0 for h in H):
        say("ERROR", "geometry.heights_m %s looks like feet / mm (metres expected)" % H)
    if not cfg.get("portal") and (geo.get("plan_x_m") is None or geo.get("plan_y_m") is None):
        say("ERROR", "geometry.plan_x_m / plan_y_m required")
    occ = cfg.get("occupancy")
    I_rec = IS.importance_factor(occ)
    if not I_rec.get("found"):
        say("ERROR", "IS 1893 Table 8: " + str(I_rec.get("note")))
    ld = cfg.get("loads") or {}
    for k in ("D_floor", "D_roof", "L_floor", "Lr"):
        if ld.get(k) is None and not cfg.get("portal"):
            say("ERROR", "loads.%s (kN/m2) required" % k)
        v = ld.get(k)
        if isinstance(v, (int, float)) and v > 25.0:
            say("ERROR", "loads.%s = %s kN/m2 implausible (psf entered?)" % (k, v))
    if ld.get("partition_seismic_kNm2") is not None and float(ld["partition_seismic_kNm2"]) < 0.5 and not cfg.get("portal"):
        say("ERROR", "partitions in W shall not be less than 0.5 kN/m2 (IS 1893 7.3.6)")
    elif ld.get("partition_seismic_kNm2") is not None and ld.get("partition_design_kNm2") is not None \
            and float(ld["partition_seismic_kNm2"]) < float(ld["partition_design_kNm2"]) - 1e-9 and not cfg.get("portal"):
        # H22 / ruling R1
        say("WARN", "loads.partition_seismic_kNm2 = %s is below the partition design allowance %s kN/m2: IS 1893 7.3.6 "
                    "'In case the minimum values of seismic weights corresponding to partitions given in parts of IS 875 are "
                    "higher, the higher values shall be used' (default when not declared: max(0.5, allowance))"
            % (ld["partition_seismic_kNm2"], ld["partition_design_kNm2"]))
    # ---- lateral system (D3 / L7) ----
    lf = cfg.get("lateral_frame")
    if cfg.get("portal"):
        po = cfg["portal"]
        if cfg.get("all_cfs_portal"):
            if po.get("seismic_basis") != "elastic_R1":
                say("ERROR", "all-CFS portal: portal.seismic_basis must be 'elastic_R1' (R = 1.0, no ductility claimed; "
                             "IS 800 Section 12 not applicable) -- owner ruling for CFS Ex5")
            if str(site.get("zone")).upper() != "II":
                say("ERROR", "all-CFS elastic portal is ruled for Zone II (Hyderabad Ex5) only; Zones III-V portals are "
                             "hot-rolled IS 800 SMF (D3)")
        elif not lf:
            say("ERROR", "portal in Zone %s needs cfg['lateral_frame'] (hot-rolled IS 800 SMF portal, D3) unless all_cfs_portal" % site.get("zone"))
    elif not lf:
        say("ERROR", "cfg['lateral_frame'] (hot-rolled IS 800 Section 12 braced / moment frame) required -- D3: no CFS SFRS")
    if lf:
        try:
            import india_cfs_lateral as L
            L.resolve_system_full(site.get("zone"), lf.get("system"), sum(float(h) for h in H) if H else None,
                                  lf.get("R_x"), lf.get("R_y"), lf.get("system_x"), lf.get("system_y"))
        except Exception as ex:
            say("ERROR", "lateral system: %s" % ex)
        for k in ("NX", "NY", "bay_x_m", "bay_y_m", "col", "beam"):
            if lf.get(k) is None:
                say("ERROR", "lateral_frame.%s required" % k)
        try:
            import india_cfs_lateral as L
            braced_sys = any(c in L.BRACED_SYSTEMS for c in L.system_components(lf.get("system")))
        except Exception:
            braced_sys = str(lf.get("system", "")).upper() in ("SCBF", "OCBF", "EBF")
        if braced_sys and not lf.get("brace"):
            say("ERROR", "lateral_frame.brace (IS 808 / IS 1161 label, IS 2062 E250 B0 per IS 800 12.8.2.1) required")
        if not lf.get("connections"):
            say("ERROR", "lateral_frame.connections (brace_end / beam_shear / column_base geometry for india_connection_design) required")
    if lf and not cfg.get("portal"):
        import india_cfs_frame_build as FB
        out += FB.framed_area_issues(cfg)                  # C06: framed floor / roof area vs the declared plan
    cm = cfg.get("cfs_members") or {}
    if not cfg.get("portal") and not cm:
        say("ERROR", "cfg['cfs_members'] (studs / joists to IS 801) required")
    if cm and cm.get("Fy_MPa") is None:
        say("ERROR", "cfs_members.Fy_MPa + grade_cite required (IS 811 has no default grade)")
    import india_cfs_members as CMB
    for role in ("studs", "joists", "purlins", "girts", "rafters", "columns", "eave_struts", "headers"):
        for spec in CMB.groups(cm, role):                   # C14: one group or a list of groups
            if spec.get("section"):
                try:
                    import is811_sections as S
                    n, base = S.parse_designator(spec.get("designator") or spec["section"])
                    S.props(base)
                except Exception as ex:
                    say("ERROR", "cfs_members.%s: %s" % (role, ex))
    if cm:
        out += CMB.wind_preflight(cfg)                      # C02: member wind derivable for studs / purlins / girts
    out += G.validate_india_cfs_p0(cfg)
    out += G.audit_warnings(cfg)                         # AUD-3 WARNs
    return out


def render(res) -> str:
    if not res:
        return "[preflight] OK -- no findings"
    return "[preflight]\n" + "\n".join("  %-5s %s" % (s, m) for s, m in res)
