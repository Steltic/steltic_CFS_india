"""india_cfs_lateral.py -- the lateral force-resisting system of an India CFS building (decision D3, spec WP3.5 as
re-ruled by the owner): a HOT-ROLLED IS 800:2007 Section 12 braced frame (Zone II OCBF R 4.0; Zones III / IV SCBF
R 4.5; Zone V EBF R 5.0 -- lead ruling L7) or an IS 800 moment frame (SMF R 5.0; in Zones IV / V only when h < 15 m,
IS 18168:2023 cl. 1.3), analysed and checked by the vendored HR India pipeline (engine3d + IS 1893 ESM / RSA +
IS 800 Table 4 combinations + IS 800 member checks + Section 12 / IS 18168 checks + india_connections bases).

The cold-formed members (studs, tracks, joists, purlins, girts) are gravity / wind members only (IS 801 WSM,
india_cfs_members); the diaphragm hands the storey inertia to the frame lines (diaphragm_demands).

cfg schema (metres, kN/m2):
  cfg['lateral_frame'] = {
      system: "SCBF" | "OCBF" | "EBF" | "SMF", R: 4.5,
      NX, NY, bay_x_m, bay_y_m,                   # hot-rolled column grid (CFS floor spans between the grid beams)
      braced_bays: "perimeter" | [["X", i, j], ...] | "core",   moment_lines: [["X", j], ["Y", i]] for SMF,
      col, beam, brace (IS 808 / IS 1161 labels), col_sec: {"lateral": {"1-2": ..}, "gravity": {..}}, beam_sec: {..},
      steel_grade, brace_grade, brace_process, brace_config, base, connections: {...HR cfg['connections']...},
      apply_is18168: bool }
  cfg['geometry']['heights_m'], cfg['loads'] {D_floor, D_roof, L_floor, Lr, clad, partition_design_kNm2,
      partition_seismic_kNm2, snow}, cfg['site'] {city, zone, Z, soil, Vb, terrain_category, cyclone_belt,
      cyclone_belt_cite, k2_table {z_m: k2} (IS 875-3 Table 2, retrieved), k1, k3, Ka_basis},
  cfg['occupancy'] (IS 1893 Table 8, D8), cfg['load_plan'] (retrieval, wind_summary, gravity_summary, ...).
"""
from __future__ import annotations
import json
import math
import os
import subprocess
import sys

import india_cfs_env  # noqa: F401  (hr_vendor on sys.path)
import india_wind_tables as WT
import india_seismic as IS

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "hr_vendor_runner.py")

# Lead ruling L7 (+ IS 1893 Table 9 with Amd 2, IS 18168:2023 cl. 1.3): the CFS lateral systems by zone
SYSTEM_BY_ZONE = {"II": ("OCBF", 4.0), "III": ("SCBF", 4.5), "IV": ("SCBF", 4.5), "V": ("EBF", 5.0)}
TABLE9_R = {"OCBF": 4.0, "OBF": 4.0, "SCBF": 4.5, "SBF": 4.5, "EBF": 5.0, "SMF": 5.0, "SMRF": 5.0, "OMF": 3.0, "OMRF": 3.0}
TABLE9_CITE = ("IS 1893 (Part 1):2016 Table 9 (Amd 2): OBF 4.0 (Note 1: not in Zones III-V), SBF concentric 4.5, "
               "SBF eccentric 5.0, steel SMRF 5.0; IS 18168:2023 1.3: Zone V EBF only; SMRF in Zones IV/V only for h < 15 m")


class LateralSystemError(ValueError):
    pass


BRACED_SYSTEMS = ("OCBF", "OBF", "SCBF", "SBF", "EBF")
MOMENT_SYSTEMS = ("SMF", "SMRF", "OMF", "OMRF")


def system_components(system):
    """'SMF+SCBF' / 'EBF + SMF' / 'SCBF' -> ['SMF', 'SCBF'] (upper-case, order kept, duplicates dropped)."""
    out = []
    for p in str(system or "").replace("&", "+").replace("/", "+").split("+"):
        p = p.strip().upper()
        if p and p not in out:
            out.append(p)
    return out


def _check_component(zone, sysn, height_m):
    if sysn in ("OCBF", "OBF", "OMF", "OMRF") and zone in ("III", "IV", "V"):
        raise LateralSystemError("%s is not permitted in Zone %s (IS 1893 Table 9 Note 1 as amended, decision D4)" % (sysn, zone))
    if sysn in ("SCBF", "SBF") and zone == "V":
        raise LateralSystemError("SCBF is not permitted in Zone V: IS 18168:2023 cl. 1.3 'all steel buildings shall be made of "
                                 "EBF systems; SCBFs shall not be used' (lead ruling L7: EBF R 5.0)")
    if sysn in ("SMF", "SMRF") and zone in ("IV", "V") and height_m is not None and height_m >= 15.0:
        raise LateralSystemError("SMRF in Zone %s only for buildings of height < 15 m (IS 18168:2023 cl. 1.3); h = %.1f m"
                                 % (zone, height_m))
    if sysn not in TABLE9_R:
        raise LateralSystemError("system %r has no IS 1893 Table 9 row (D3: no foreign design basis)" % sysn)


def resolve_system_full(zone, system=None, height_m=None, R_x=None, R_y=None, system_x=None, system_y=None):
    """C10: a single or MIXED system ('SMF+SCBF', 'EBF+SMF', ...).  Every component passes the zone gate; R = min over
    the components (IS 1893 Table 9 via the least-ductile component) unless per-direction R_x / R_y are declared -- each
    validated against the Table 9 R of that direction's system (system_x / system_y when given, else every component),
    the same rule as the HR india_seismic_gates.resolve_system_R.  Returns {system, components, R, R_x, R_y, cite, ...}."""
    zone = str(zone).upper()
    if zone not in SYSTEM_BY_ZONE:
        raise LateralSystemError("zone %r not in II-V" % zone)
    comps = system_components(system) or [SYSTEM_BY_ZONE[zone][0]]
    for c in comps:
        _check_component(zone, c, height_m)
    R = min(TABLE9_R[c] for c in comps)
    out = {"system": "+".join(comps), "components": comps, "mixed": len(comps) > 1, "R": R, "cite": TABLE9_CITE,
           "braced": any(c in BRACED_SYSTEMS for c in comps), "moment": any(c in MOMENT_SYSTEMS for c in comps)}
    for d, decl, dsys in (("x", R_x, system_x), ("y", R_y, system_y)):
        dcomps = system_components(dsys) if dsys else comps
        for c in dcomps:
            _check_component(zone, c, height_m)
            if c not in comps:
                raise LateralSystemError("system_%s component %s is not part of the declared system %s" % (d, c, out["system"]))
        Rt = min(TABLE9_R[c] for c in dcomps)
        out["R_%s_table9" % d] = Rt
        if decl is not None:
            if float(decl) > Rt + 1e-9:
                raise LateralSystemError("R_%s = %s exceeds the IS 1893 Table 9 value %s for the %s-direction system %s"
                                         % (d, decl, Rt, d.upper(), "+".join(dcomps)))
            out["R_" + d] = float(decl)
            out["R_%s_declared" % d] = True
        else:
            out["R_" + d] = R
            out["R_%s_declared" % d] = False
    if out["mixed"]:
        out["cite"] = TABLE9_CITE + "; mixed system %s: R = min over the components (%s) unless R_x / R_y are declared" % (
            out["system"], ", ".join("%s %s" % (c, TABLE9_R[c]) for c in comps))
    return out


def resolve_system(zone, system=None, height_m=None):
    """Return (system, R, cite) for a CFS building's hot-rolled frame in a zone; refuse banned combinations.  Mixed
    systems ('SMF+SCBF') return the joined label and R = min over the components (C10)."""
    r = resolve_system_full(zone, system, height_m)
    return r["system"], r["R"], r["cite"]


def _k2(site, z_m):
    tab = site.get("k2_table")
    if not tab:
        raise LateralSystemError("site.k2_table {z_m: k2} (IS 875-3 Table 2 for the terrain category, retrieved from the "
                                 "corpus) missing -- k2 is never guessed")
    pts = sorted((float(k), float(v)) for k, v in dict(tab).items())
    if z_m <= pts[0][0]:
        return pts[0][1]
    for (z1, k1), (z2, k2) in zip(pts, pts[1:]):
        if z1 <= z_m <= z2:
            return k1 + (k2 - k1) * (z_m - z1) / (z2 - z1)
    return pts[-1][1]


# DOCS-OPEN-1: the site record that makes a Vb / zone reading acceptable to the HR preflight -- the map reading
# ('derived_from_map' with the site lat / long) or the ruling R5 site proxy (proxy_town, distance_km, basis, verify,
# annex_found / corpus_status; india_loads.resolve_site_annex_proxy) -- forwarded to the HR sub-run
SITE_PROXY_KEYS = ("proxy_town", "distance_km", "basis", "verify", "annex_found", "corpus_status")


def site_source_record(site, quantity="Vb"):
    """{<q>_source, lat, long, proxy_town, distance_km, basis, verify, annex_found, corpus_status} declared on the CFS
    site for quantity 'Vb' or 'zone': top-level site keys, overridden by a nested site['site_proxy'] record and by the
    quantity-specific site['Vb_site_proxy'] / site['zone_site_proxy'] record (a nested record may also give 'cite' for
    the basis).  Only the keys actually declared are returned."""
    site = site or {}
    q = "Vb" if str(quantity).lower().startswith("vb") else "zone"
    rec = {}
    src = site.get("%s_source" % q)
    if src is not None:
        rec["%s_source" % q] = src
    for a, b in (("lat", "lat"), ("latitude", "lat"), ("long", "long"), ("lon", "long"), ("longitude", "long")):
        if site.get(a) is not None and b not in rec:
            rec[b] = site[a]
    for k in SITE_PROXY_KEYS:
        if site.get(k) is not None:
            rec[k] = site[k]
    for nest in (site.get("site_proxy"), site.get("%s_site_proxy" % q)):
        if isinstance(nest, dict):
            for k in SITE_PROXY_KEYS + ("lat", "long"):
                if nest.get(k) is not None:
                    rec[k] = nest[k]
            if nest.get("cite") is not None and "basis" not in rec:
                rec["basis"] = nest["cite"]
            if nest.get("source") is not None and "%s_source" % q not in rec:
                rec["%s_source" % q] = nest["source"]
    return rec


def wind_story_forces(cfg):
    """IS 875 (Part 3):2015 storey forces on the whole building (N) for wind along X and along Y, from Vb, k1, k2(z)
    (Table 2, retrieved), k3, k4 / Kd (cyclone belt, D10), Ka (Table 4, frame tributary area), Kc, Table 5 wall
    Cpe (windward - leeward; Cpi cancels for the overall shear).  Returns dict for load_plan.wind_summary +
    story_forces W_X / W_Y."""
    site = cfg["site"]; geo = cfg["geometry"]
    H = list(geo["heights_m"]); Lx, Ly = float(geo["plan_x_m"]), float(geo["plan_y_m"])
    Vb = float(site["Vb"]); k1 = float(site.get("k1", 1.0)); k3 = float(site.get("k3", 1.0))
    cb = site.get("cyclone_belt")
    if cb is None:
        raise LateralSystemError("site.cyclone_belt (true/false + cite) required (D10: Kd and k4 from the same flag)")
    req = WT.k4_required(bool(cb), site.get("wind_structure_class"))
    k4 = req["k4"]; Kd = 1.0 if cb else float(site.get("Kd", 0.9))
    Kc = float(site.get("Kc", 1.0))
    out = {"code": "IS 875 (Part 3):2015", "Vb_mps": Vb, "Vb_source": site.get("Vb_source", "Annex A"), "k1": k1, "k3": k3,
           "k4": k4, "k4_cite": req.get("cite"), "structure_class": req.get("class") or str(site.get("wind_structure_class") or "other"),
           "Kd": Kd, "Kc": Kc, "cyclone_belt": bool(cb), "cyclone_belt_cite": site.get("cyclone_belt_cite"),
           "terrain_category": site.get("terrain_category"), "Ka_basis": "frame_tributary", "storeys": []}
    out.update(site_source_record(site, "Vb"))          # DOCS-OPEN-1: lat / long or the R5 site-proxy record
    out.setdefault("Vb_source", "Annex A")
    hs = []
    z = 0.0
    for h in H:
        z += h; hs.append(z)
    # frame tributary area for Ka (7.2.2.1 (a)), PER DIRECTION (C02 / CFS-D-10): the frames resisting wind along X are
    # the lines y = const, spaced bay_y apart -> A = bay_y x storey height (and bay_x for wind along Y)
    lf = cfg.get("lateral_frame") or {}
    Ka_d = {}
    for d, bay_key, Lalt in (("X", "bay_y_m", Ly), ("Y", "bay_x_m", Lx)):
        sp = float(lf.get(bay_key) or Lalt)
        # RR-BUG-6: a declared site.Ka_corpus_hit is per direction (Ka_x / Ka_y, or an {area: Ka} table) or is checked
        # against Table 4 at THIS direction's area -- never applied where Table 4 gives a higher Ka
        Ka_rec = WT.resolve_ka(sp * max(H), site.get("Ka_corpus_hit"), direction=d)
        if not Ka_rec.get("found"):
            raise LateralSystemError("Ka (Table 4) unresolved: %s" % Ka_rec.get("cite"))
        Ka_d[d] = (float(Ka_rec["Ka"]), sp * max(H), Ka_rec.get("cite"))
        out.update({"Ka_%s" % d: Ka_d[d][0], "Ka_area_%s_m2" % d: Ka_d[d][1]})
        if Ka_rec.get("area_check"):
            out["Ka_area_check_%s" % d] = Ka_rec["area_check"]
        if Ka_rec.get("note"):
            out["Ka_note_%s" % d] = Ka_rec["note"]
    dgov = max(Ka_d, key=lambda d: Ka_d[d][0])
    out.update(Ka=Ka_d[dgov][0], Ka_area_m2=Ka_d[dgov][1], Ka_cite=Ka_d[dgov][2],
               Ka_note="Ka per direction: frame spacing normal to the wind x storey height (7.2.2.1); Ka / Ka_area = the larger")
    # C05: optional per-level exposed face (mixed-height buildings): geometry.wind_exposure = {level: {width_X_m,
    # width_Y_m, height_m}} -- width_X_m = the face width loaded by wind along X, height_m = the tributary height
    expo = {str(k): v for k, v in dict(geo.get("wind_exposure") or {}).items()}
    forces = {"W_X": {}, "W_Y": {}}
    htot = sum(H)
    w_, l_ = min(Lx, Ly), max(Lx, Ly)          # Table 5: w = lesser, l = greater plan dimension
    for d, B in (("X", Ly), ("Y", Lx)):
        # theta = 0: wind normal to the long face (faces A/B windward/leeward); theta = 90: normal to the short face (C/D)
        theta = 0.0 if B == l_ else 90.0
        cpe = WT.resolve_cpe_walls(htot / w_, l_ / w_, theta, site.get("cpe_corpus_hit"))
        if not cpe.get("found"):
            raise LateralSystemError("Table 5 wall Cpe unresolved for h/w = %.2f, l/w = %.2f, theta %g: %s"
                                     % (htot / w_, l_ / w_, theta, cpe.get("cite")))
        A_, B_ = (cpe["Cpe"]["A"], cpe["Cpe"]["B"]) if theta == 0.0 else (cpe["Cpe"]["C"], cpe["Cpe"]["D"])
        net = A_ - B_
        out["Cpe_%s" % d] = {"windward": A_, "leeward": B_, "net": net, "cite": cpe.get("cite"), "h_over_w": htot / w_,
                             "l_over_w": l_ / w_, "theta_deg": theta, "face_width_m": B}
        Ka = Ka_d[d][0]
        for k, h in enumerate(H, start=1):
            roof = k == len(H)
            ztop = hs[k - 1]
            k2 = _k2(site, ztop)
            Vz = Vb * k1 * k2 * k3 * k4
            pz = 0.6 * Vz ** 2 / 1000.0            # kN/m2
            pd = max(Kd * Ka * Kc * pz, 0.70 * pz)
            trib = H[k - 1] / 2.0 + (H[k] / 2.0 if k < len(H) else 0.0)     # half storey below + half above
            ex = expo.get(str(k)) or {}
            Bk = float(ex.get("width_%s_m" % d) or B)
            if ex.get("height_m") is not None:
                trib = float(ex["height_m"])
            F = net * pd * Bk * trib * 1000.0      # N
            forces["W_" + d][str(k)] = [F if d == "X" else 0.0, F if d == "Y" else 0.0, 0.0]
            if d == "X":
                out["storeys"].append({"k": k, "z_m": ztop, "k2": round(k2, 4), "Vz_mps": round(Vz, 3), "pz_kNm2": round(pz, 4),
                                       "pd_X_kNm2": round(pd, 4), "trib_h_m": trib, "face_width_X_m": Bk})
            else:
                row = out["storeys"][k - 1]
                row.update(pd_Y_kNm2=round(pd, 4), face_width_Y_m=Bk, pd_kNm2=max(row["pd_X_kNm2"], round(pd, 4)))
    if expo:
        out["wind_exposure"] = expo
    out["pz_kNm2"] = max(s["pz_kNm2"] for s in out["storeys"]); out["pd_kNm2"] = max(s["pd_kNm2"] for s in out["storeys"])
    out["VB_x_kN"] = sum(v[0] for v in forces["W_X"].values()) / 1e3
    out["VB_y_kN"] = sum(v[1] for v in forces["W_Y"].values()) / 1e3
    out["cite"] = ("IS 875-3 6.2 Vb (Annex A); 6.3 Vz = Vb k1 k2 k3 k4; Table 2 k2; 6.3.4 k4; 7.2 pz = 0.6 Vz^2, pd = Kd Ka Kc pz "
                   ">= 0.7 pz; 7.2.1 Kd; Table 4 Ka (frame tributary); Table 5 Cpe; 7.3.2 Cpi cancels for the overall shear")
    return out, forces


def lowrise_member_wind_plan(cfg, ws, plan):
    """C02 / CFS-C-07 / CFS-D-09(b): load_plan['member_wind'] for a single-storey / low-rise HR lateral run (the HR
    preflight requires it and the wall columns then carry the girt reactions of the Table 5 wall pressures), from the
    vendored india_wind_tables.lowrise_member_wind: Table 5 walls, Table 6 roof by pitch, Cpi from the opening ratio
    (7.3.2).  A declared member_wind is kept.  Returns (patterns, basis) or None when not a low-rise run."""
    geo = cfg["geometry"]; lf = cfg.get("lateral_frame") or {}
    H = list(geo["heights_m"])
    if plan.get("member_wind"):
        return None
    lowrise = len(H) == 1 or bool(lf.get("member_wind")) or geo.get("roof_pitch_deg") is not None
    if not lowrise or lf.get("member_wind") is False:
        return None
    Lx, Ly = float(geo["plan_x_m"]), float(geo["plan_y_m"])
    w_, l_ = min(Lx, Ly), max(Lx, Ly)
    top = ws["storeys"][-1]
    pd = max(float(top.get("pd_X_kNm2") or 0.0), float(top.get("pd_Y_kNm2") or 0.0), float(top.get("pd_kNm2") or 0.0))
    orat = geo.get("opening_ratio", (cfg.get("site") or {}).get("opening_ratio"))
    pitch = float(geo.get("roof_pitch_deg") or 0.0)
    ridge = "X" if Lx >= Ly else "Y"                          # the ridge runs along the greater plan dimension
    mw = WT.lowrise_member_wind(pd, sum(H), w_, l_, pitch, 0.05 if orat is None else float(orat), ridge_axis=ridge)
    if not isinstance(mw, dict) or not mw.get("found"):
        raise LateralSystemError("low-rise member wind (IS 875-3 Tables 5 / 6, 7.3.2) unresolved: %s"
                                 % (mw.get("note") if isinstance(mw, dict) else mw))
    basis = {"pd_kNm2": pd, "h_m": sum(H), "w_m": w_, "l_m": l_, "roof_pitch_deg": pitch, "ridge_axis": ridge,
             "opening_ratio": orat, "opening_ratio_note": None if orat is not None else
             "geometry.opening_ratio not declared: 5 % assumed (Cpi +-0.2, IS 875-3 7.3.2.1) -- VERIFY",
             "cite": str(mw.get("cite")) + "; pd = the roof-storey frame pd (Table 4 frame Ka)",
             "source": "india_wind_tables.lowrise_member_wind (vendored)"}
    return mw["patterns"], basis


def merge_declared_wind(plan, forces):
    """C05: a declared load_plan.story_forces W_X / W_Y (e.g. a mixed-height building worked by hand from IS 875-3) is
    KEPT, not overwritten by the envelope storey forces -- it needs a cite (story_forces_cite or wind_story_forces_cite)
    and story_forces_units ('N' | 'kN').  Returns (story_forces in N, {W_X: source, W_Y: source})."""
    plan = plan or {}
    decl = dict(plan.get("story_forces") or {})
    units = str(plan.get("story_forces_units") or "").lower()
    cite = plan.get("wind_story_forces_cite") or plan.get("story_forces_cite")
    out = dict(decl)
    src = {}
    prev = ((plan.get("wind_summary") or {}).get("story_forces_source") or {})
    for ref in ("W_X", "W_Y"):
        generated = str(prev.get(ref) or "").startswith("IS 875-3 storey forces")    # a re-run: our own earlier output
        if decl.get(ref) and not generated:
            if not cite:
                raise LateralSystemError("load_plan.story_forces.%s declared without a cite (wind_story_forces_cite): a declared "
                                         "storey wind replaces the IS 875-3 envelope forces only with its source" % ref)
            if units not in ("n", "kn"):
                raise LateralSystemError("load_plan.story_forces.%s declared without story_forces_units ('N' or 'kN')" % ref)
            f = 1000.0 if units == "kn" else 1.0
            out[ref] = {str(k): [float(x) * f for x in v] for k, v in dict(decl[ref]).items()}
            src[ref] = "declared (%s)" % cite
        else:
            out[ref] = forces[ref]
            src[ref] = "IS 875-3 storey forces (india_cfs_lateral.wind_story_forces)"
    for ref, v in list(out.items()):                          # other declared references (EQ_*) to N as well
        if ref not in ("W_X", "W_Y") and units == "kn" and isinstance(v, dict):
            out[ref] = {str(k): [float(x) * 1000.0 for x in vv] for k, vv in v.items()}
    return out, src


def partition_seismic_default(ld):
    """IS 1893 7.3.6 (ruling R1): partitions in the seismic weight = the declared partition_seismic_kNm2, else
    max(0.5, partition_design_kNm2) ('not less than 0.5 kN/m2 ... the higher values shall be used')."""
    ld = ld or {}
    if ld.get("partition_seismic_kNm2") is not None:
        return float(ld["partition_seismic_kNm2"])
    return max(0.5, float(ld.get("partition_design_kNm2") or 0.0))


def hr_retrieval_rows(rows):
    """FIX1: the CFS retrieval row names its stored hit as 'file' (e.g. 'rag/IS1893_table9_SBF.json'); the vendored HR
    evidence gate (consistency.rag_evidence_issues, H30) reads 'hit_file' + 'quote'.  Map file -> hit_file exactly as the
    CFS-level check does (consistency.rag_evidence), so the lateral sub-run checks the same stored hit -- never drop a row
    or its found flag."""
    if not isinstance(rows, list):
        return rows
    out = []
    for h in rows:
        if isinstance(h, dict) and h.get("file") and not h.get("hit_file"):
            h = dict(h)
            f = str(h["file"])
            h["hit_file"] = f.split("rag/", 1)[-1] if "rag/" in f else f
        out.append(h)
    return out


def copy_rag_hits(rag_dir, sub_root):
    """FIX1: the HR sub-run is its own job folder (<job>/lateral/<name>); its consistency gate looks for the stored
    retrieval hits in <sub_root>/rag/.  Copy the parent job's rag/ there (files only, the parent copy stays the record).
    Returns the number of files copied."""
    import shutil
    if not rag_dir or not os.path.isdir(rag_dir):
        return 0
    dst = os.path.join(sub_root, "rag")
    n = 0
    for dp, dn, fn in os.walk(rag_dir):
        rel = os.path.relpath(dp, rag_dir)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in fn:
            shutil.copy2(os.path.join(dp, f), os.path.join(dst, rel, f))
            n += 1
    return n


def build_hr_spec(cfg, name):
    """Declarative HR-frame spec (JSON) from the CFS cfg."""
    lf = cfg["lateral_frame"]; site = cfg["site"]; geo = cfg["geometry"]; ld = cfg["loads"]
    H = list(geo["heights_m"])
    rs = resolve_system_full(site["zone"], lf.get("system"), sum(H), lf.get("R_x"), lf.get("R_y"),
                             lf.get("system_x"), lf.get("system_y"))
    sysn, R, cite = rs["system"], rs["R"], rs["cite"]
    if lf.get("R") is not None and abs(float(lf["R"]) - R) > 1e-9:
        raise LateralSystemError("lateral_frame.R = %s but IS 1893 Table 9 gives %s for %s" % (lf["R"], R, sysn))
    I_rec = IS.importance_factor(cfg.get("occupancy"))
    if not I_rec.get("found"):
        raise LateralSystemError("IS 1893 Table 8 importance factor unresolved: %s" % I_rec.get("note"))
    NX, NY = int(lf["NX"]), int(lf["NY"])
    bays = lf.get("braced_bays", "perimeter")
    if bays == "perimeter":
        bays = [["X", i, 0] for i in range(NX)] + [["X", i, NY] for i in range(NX)] + \
               [["Y", 0, j] for j in range(NY)] + [["Y", NX, j] for j in range(NY)]
    elif bays == "core":
        bays = [["X", NX // 2, NY // 2], ["Y", NX // 2, NY // 2]]
    if not rs["braced"]:
        bays = []                                           # pure moment frame: no braced bays
    # C10: a mixed system (SMF+SCBF, EBF+SMF) keeps its declared braced bays and its moment lines
    ws, forces = wind_story_forces(cfg)
    plan = dict(cfg.get("load_plan") or {})
    plan["jurisdiction"] = "india"
    plan["wind_summary"] = dict(plan.get("wind_summary") or {}, **ws)
    plan["gravity_summary"] = dict(plan.get("gravity_summary") or {},
                                   D_floor_kNm2=ld["D_floor"], D_roof_kNm2=ld["D_roof"], L_floor_kNm2=ld["L_floor"],
                                   L_roof_kNm2=ld["Lr"], clad_kNm2=ld.get("clad", 0.0),
                                   partition_kNm2=ld.get("partition_design_kNm2", 0.0), snow_kNm2=ld.get("snow", 0.0))
    mwp = lowrise_member_wind_plan(cfg, ws, plan)
    if mwp is not None:
        plan["member_wind"], plan["wind_summary"]["member_wind_basis"] = mwp
    plan["story_forces"], ws["story_forces_source"] = merge_declared_wind(plan, forces)
    plan["wind_summary"].update(story_forces_source=ws["story_forces_source"])
    plan["story_forces_units"] = "N"
    plan["seismic_summary"] = dict(plan.get("seismic_summary") or {}, code=IS.IS1893_EDITION if hasattr(IS, "IS1893_EDITION") else "IS 1893 (Part 1):2016",
                                   site=site.get("city"), zone=site["zone"], Z=site["Z"], I=I_rec["I"], I_cite=I_rec.get("cite"),
                                   I_row=I_rec.get("row"), R=R, R_cite=cite, system=sysn, soil=site["soil"],
                                   **site_source_record(site, "zone"),    # DOCS-OPEN-1: zone_source + map / R5 record
                                   **({"R_x": rs["R_x"], "R_y": rs["R_y"]} if (rs["R_x_declared"] or rs["R_y_declared"]) else {}))
    plan["combinations"] = "auto"
    plan["lateral_frame_basis"] = "IS800_LSD"
    plan.pop("cfs_combinations", None)                      # the HR run sees only the IS 800 set
    plan["retrieval"] = hr_retrieval_rows(plan.get("retrieval"))
    spec = {
        "name": name, "system": sysn, "system_components": rs["components"], "R": R,
        "R_x": rs["R_x"] if rs["R_x_declared"] else None, "R_y": rs["R_y"] if rs["R_y_declared"] else None,
        "system_x": lf.get("system_x"), "system_y": lf.get("system_y"), "Z": site["Z"], "I": I_rec["I"], "zone": site["zone"], "soil": site["soil"],
        "NX": NX, "NY": NY, "bay_x_m": float(lf["bay_x_m"]), "bay_y_m": float(lf["bay_y_m"]), "heights_m": H,
        "D_floor": ld["D_floor"], "D_roof": ld["D_roof"], "L_floor": ld["L_floor"], "Lr": ld["Lr"], "clad": ld.get("clad", 0.0),
        "snow": ld.get("snow", 0.0), "partition_design_kNm2": ld.get("partition_design_kNm2", 0.0),
        # H22 / ruling R1: partitions in W default to max(0.5, the partition design allowance) (IS 1893 7.3.6)
        "partition_seismic_kNm2": partition_seismic_default(ld), "partitions": ld.get("partitions", True),
        "braced_bays": bays, "moment_lines": lf.get("moment_lines") or [], "col": lf["col"], "beam": lf["beam"],
        "brace": lf.get("brace"), "col_sec": lf.get("col_sec") or {}, "beam_sec": lf.get("beam_sec") or {},
        "steel_grade": lf.get("steel_grade", "E250 B0"), "brace_grade": lf.get("brace_grade", "E250 B0"),
        "brace_process": lf.get("brace_process"), "brace_config": lf.get("brace_config", "X"), "base": lf.get("base", "fixed"),
        "diaphragm": lf.get("diaphragm", "rigid"), "deck_span": lf.get("deck_span", "Y"),
        "floor_system": lf.get("floor_system", "one-way: CFS joists (IS 801) span between the hot-rolled grid beams"),
        "connections": lf.get("connections") or {}, "apply_is18168": lf.get("apply_is18168", site["zone"] in ("III", "IV", "V")),
        "section12_inputs": lf.get("section12_inputs") or {}, "K_factors": lf.get("K_factors"),
        "LLT_sag_mm": lf.get("LLT_sag_mm"), "LLT_hog_mm": lf.get("LLT_hog_mm"), "collector_basis": lf.get("collector_basis"),
        "occupancy": cfg.get("occupancy"), "load_plan": plan, "diaphragm_7_6_4": lf.get("diaphragm_7_6_4"),
        "gold": lf.get("gold"), "custom_build_module": lf.get("custom_build_module"),      # job-local builder (irregular plans)
        "d_x_m": lf.get("d_x_m"), "d_y_m": lf.get("d_y_m"), "default_strong": lf.get("default_strong"), "Ta_override": lf.get("Ta_override"),
        # X01: IS 1893 Table 5(ii) flexible-diaphragm run of the HR engine (L / T / U / Z / cruciform plans): the declared
        # in-plane deck stiffness, the explicit run switch and an EOR record of an external analysis
        "diaphragm_stiffness": lf.get("diaphragm_stiffness"), "flexible_diaphragm_analysis": lf.get("flexible_diaphragm_analysis"),
        "flexible_diaphragm_eor": lf.get("flexible_diaphragm_eor"),
        # AUD-3: deck kind for the IS 1893 7.6.4 preflight rule of the HR run
        "diaphragm_type": lf.get("diaphragm_type"),
        "hr_cfg_extra": lf.get("hr_cfg_extra") or {},       # declared HR cfg keys passed through verbatim (e.g. is18168_table2,
                                                            # grade_by_section, custom_sections, column_imposed_load_reduction)
        "notes": "%s: hot-rolled %s lateral frame (R %s) of a CFS building; CFS members gravity / wind only (D3)"
                 % (name, sysn, R),
    }
    return spec


def run_lateral(cfg, job_dir, name=None, timeout_s=3600, rag_dir=None):
    """Build the HR spec, run the vendored HR pipeline in a subprocess and return the lateral result summary.
    rag_dir: the parent job's stored retrieval hits (default <job_dir>/../rag); copied into the sub-run's own rag/ so
    the HR evidence gate sees the hits that the load_plan retrieval rows cite (FIX1)."""
    name = name or (cfg.get("name") or "job") + "_lateral"
    os.makedirs(job_dir, exist_ok=True)
    if rag_dir is None:
        rag_dir = os.path.join(os.path.dirname(os.path.abspath(job_dir)), "rag")
    copy_rag_hits(rag_dir, os.path.join(job_dir, name))
    spec = build_hr_spec(cfg, name)
    spec_path = os.path.join(job_dir, "lateral_frame_spec.json")
    json.dump(spec, open(spec_path, "w"), indent=1, default=str)
    cmd = [sys.executable, RUNNER, spec_path, job_dir, name]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, env=env)
    log = os.path.join(job_dir, "lateral_run.log")
    with open(log, "w") as f:
        f.write(proc.stdout); f.write("\n--- stderr ---\n"); f.write(proc.stderr)
    rp = os.path.join(job_dir, name, "lateral_result.json")
    if not os.path.exists(rp):
        raise LateralSystemError("HR lateral run produced no result (see %s):\n%s" % (log, proc.stderr[-2000:]))
    res = json.load(open(rp))
    res["spec"] = spec_path; res["log"] = log; res["name"] = name
    res["vendored_commit"] = india_cfs_env.vendored_commit()
    return res


def _per_storey(v, k, default=None):
    """A number, or {storey: value} (keys int / str, optional 'default') -> the value for storey k."""
    if isinstance(v, dict):
        for key in (k, str(k)):
            if key in v:
                return v[key]
        for rng, val in v.items():                          # '1-3' ranges
            a_, _, b_ = str(rng).partition("-")
            if a_.isdigit() and b_.isdigit() and int(a_) <= k <= int(b_):
                return val
        return v.get("default", default)
    return v if v is not None else default


def _flexible_764(lateral, d, k):
    """X01: the HR flexible-diaphragm run's IS 1893 7.6.4 record (in-plane deformation from the chord vs the average
    storey drift) of storey k, direction d -- None when the HR run did not perform the Table 5(ii) analysis."""
    lv = ((((lateral or {}).get("diaphragm_7_6_4") or {}).get("flexible_run") or {}).get("levels") or {}).get(d) or []
    for r in lv:
        if isinstance(r, dict) and int(r.get("level", -1)) == int(k):
            return {q: r.get(q) for q in ("delta_max_from_chord_mm", "avg_storey_drift_mm", "ratio", "limit",
                                          "classification")}
    return None


def diaphragm_demands(cfg, lateral):
    """Storey diaphragm demands handed from the CFS floor / roof to the frame lines (IS 1893 7.6.3 storey forces at
    gamma 1.0, IS 875-3 wind storey forces): unit shear into the frame lines of each direction and the chord force
    M/depth.  Capacities of a sheathed / decked CFS diaphragm need a cited product / test value -- IS 801 has no
    diaphragm provision (9.1.4) -- so each capacity slot is found:false until the EOR supplies one.
    C03: one braced line is allowed (v = F/B, cantilever chord); geometry.diaphragm_lines_X / _Y and
    diaphragm_capacity.v_allow_kN_per_m may be per storey ({storey: value}); collector rows at the declared
    re-entrant lines (geometry.reentrant_lines_X / _Y) carry F (1 - B_short/B)."""
    geo = cfg["geometry"]; H = list(geo["heights_m"])
    Lx, Ly = float(geo["plan_x_m"]), float(geo["plan_y_m"])
    lp = json.load(open(os.path.join(lateral["root"], "load_plan.json"))) if os.path.exists(os.path.join(lateral["root"], "load_plan.json")) else {}
    sf = lp.get("story_forces") or {}
    lf = cfg.get("lateral_frame") or {}
    NX, NY = int(lf["NX"]), int(lf["NY"])
    bx, by = float(lf.get("bay_x_m") or Lx / max(NX, 1)), float(lf.get("bay_y_m") or Ly / max(NY, 1))
    # braced lines per direction (a line = a grid line with at least one braced bay); "perimeter" / "core" as in build_hr_spec
    bays = lf.get("braced_bays", "perimeter")
    if bays == "perimeter":
        bays = [["X", i, 0] for i in range(NX)] + [["X", i, NY] for i in range(NX)] + [["Y", 0, j] for j in range(NY)] + [["Y", NX, j] for j in range(NY)]
    elif bays == "core":
        bays = [["X", NX // 2, NY // 2], ["Y", NX // 2, NY // 2]]
    lines = {"X": sorted({int(b[2]) for b in bays if b[0] == "X"}), "Y": sorted({int(b[1]) for b in bays if b[0] == "Y"})}
    for d in ("X", "Y"):
        for (dd, kk) in (lf.get("moment_lines") or []):
            if dd == d:
                lines[d] = sorted(set(lines[d]) | {int(kk)})
    dcap = cfg.get("diaphragm_capacity") or {}
    rows = []
    for k in range(1, len(H) + 1):
        # storey force along X is resisted by the frame lines that run along X (y = const, length Lx = the diaphragm
        # depth B); with n equal lines at spacing s = Lspan / (n - 1) the rigid diaphragm hands F / n to each line:
        # v = F / (n B); chord = w s^2 / (8 B) with w = F / Lspan (continuous-diaphragm approximation; n = 2 is the
        # simple span F / (2 B), F Lspan / (8 B)).  n = 1: the whole F goes into the one line (v = F / B) and the
        # diaphragm cantilevers from it: chord = w a^2 / (2 B), a = the longer overhang (a = L/2 for a central line:
        # F L / 8).  WP6-fix: B and Lspan were swapped; C03: max(2, n) halved the shear of a single line.
        for d, B, Lspan, bay in (("X", Lx, Ly, by), ("Y", Ly, Lx, bx)):
            # non-rectangular plans: depth (line length) and span declared per direction
            B = float(_per_storey(geo.get("diaphragm_depth_%s_m" % d), k) or B)
            Lspan = float(_per_storey(geo.get("diaphragm_span_%s_m" % d), k) or Lspan)
            ndecl = _per_storey(geo.get("diaphragm_lines_%s" % d), k)
            nlines = int(ndecl or len(lines[d]) or 2)
            if nlines < 1:
                raise LateralSystemError("geometry.diaphragm_lines_%s = %s at storey %d: at least one frame line" % (d, ndecl, k))
            Fe = abs(float((sf.get("EQ_" + d) or {}).get(str(k), [0, 0, 0])[0 if d == "X" else 1]))
            Fw = abs(float((sf.get("W_" + d) or {}).get(str(k), [0, 0, 0])[0 if d == "X" else 1]))
            F = max(Fe, Fw); gov = "EQ" if Fe >= Fw else "W"
            v_unit = F / 1e3 / (nlines * B)   # kN/m along each of the n frame lines (length B = diaphragm depth)
            w = F / Lspan                     # N/m
            if nlines == 1:
                pos = (lines[d][0] * bay) if (len(lines[d]) == 1 and not ndecl) else Lspan / 2.0
                a_ = max(pos, Lspan - pos)
                M = w * a_ ** 2 / 2.0         # N-m: cantilever each side of the single line
                s_span = a_
                mech = "single line: v = F/B, chord = (F/L) a^2/(2 B), a = %.2f m overhang" % a_
            else:
                s_span = Lspan / (nlines - 1)
                M = w * s_span ** 2 / 8.0     # N-m: diaphragm panel of span s between adjacent lines
                mech = "n = %d equal lines: v = F/(n B), chord = (F/L) s^2/(8 B), s = L/(n - 1)" % nlines
            chord = M / B                     # N
            cap = _per_storey(dcap.get("v_allow_kN_per_m"), k)
            ccite = dcap.get("cite")
            if isinstance(cap, dict):
                ccite = cap.get("cite") or ccite
                cap = cap.get("value")
            rec_cap = {"capacity": None, "capacity_basis": "test", "allowable_increase": 1.0, "dc": None, "ok": None, "found": False}
            if cap:
                inc = float(dcap.get("allowable_increase", 1.0))
                rec_cap = {"capacity": float(cap) * inc, "value": v_unit, "limit": float(cap) * inc, "capacity_basis": dcap.get("basis", "test"),
                           "allowable_increase": inc, "dc": v_unit / (float(cap) * inc), "ok": v_unit <= float(cap) * inc, "found": True,
                           "capacity_cite": ccite, "capacity_source": dcap.get("source")}
            rows.append({"storey": k, "dir": d, "F_EQ_N": Fe, "F_W_N": Fw, "governing": gov, "F_N": F, "n_lines": nlines,
                         "v_unit_kN_per_m": v_unit, "chord_force_kN": chord / 1e3, "span_m": Lspan, "panel_span_m": s_span, "depth_m": B, **rec_cap,
                         "clause": "IS 1893 7.6.3 storey force (gamma 1.0) / IS 875-3 storey wind; rigid diaphragm on the frame lines: " + mech,
                         "note": "diaphragm shear capacity requires a cited test / product value for the deck or sheathing "
                                 "(IS 801 9.1.4 excludes diaphragms; no Indian table) -- EOR input"})
            fr = _flexible_764(lateral, d, k)
            if fr:
                rows[-1]["flexible_run_7_6_4"] = fr          # X01: in-plane deformation measured on the HR flexible run
            # C03 / CFS-C-17: collectors (drag struts) at declared re-entrant lines
            for rl in (geo.get("reentrant_lines_%s" % d) or []):
                st_ = rl.get("storeys") or rl.get("storey")
                if st_ not in (None, "all"):
                    sts = st_ if isinstance(st_, (list, tuple)) else [st_]
                    if k not in [int(x) for x in sts]:
                        continue
                Bs = float(rl["B_short_m"]); Bf = float(rl.get("B_m") or B)
                Fc = F * max(0.0, 1.0 - Bs / Bf)
                crow = {"storey": k, "dir": d, "kind": "collector", "line": rl.get("line"), "F_N": F, "B_short_m": Bs, "B_m": Bf,
                        "value": Fc / 1e3, "F_collector_kN": Fc / 1e3, "demand_level": "working",
                        "clause": "re-entrant corner collector (drag strut): F (1 - B_short/B) of the storey force is dragged "
                                  "across the re-entrant line into the frame line (IS 1893 7.6.3 storey force / IS 875-3 storey wind)",
                        "limit": None, "dc": None, "ok": None, "found": False, "capacity_basis": rl.get("capacity_basis", "EOR_input"),
                        "allowable_increase": 1.0,
                        "note": "collector capacity: declare reentrant_lines_%s[].capacity_kN + cite (working-stress capacity of the "
                                "drag member / its connections)" % d}
                if rl.get("capacity_kN"):
                    capk = float(rl["capacity_kN"])
                    crow.update(limit=capk, capacity=capk, dc=(Fc / 1e3) / capk, ok=(Fc / 1e3) <= capk + 1e-9, found=True,
                                capacity_cite=rl.get("cite"), note=None)
                rows.append(crow)
    return rows
