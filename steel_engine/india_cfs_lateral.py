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
        # GOLD-COLL: per-level diaphragm labels (a composite podium rigid under flexible CFS floors)
        "diaphragm_by_level": lf.get("diaphragm_by_level"),
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
        # AUD-3 / AUD-4: deck kind for the 7.6.4 preflight rule and the job's delegated-design register (anchor
        # breakout / pedestal item) for the concrete_breakout record of the bases
        "diaphragm_type": lf.get("diaphragm_type"), "delegated_design": cfg.get("delegated_design"),
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


RATIO_764_NOTE = ("IS 1893 (Part 1):2016 7.6.4 literal: maximum deviation from the chord of the deformed shape / "
                  "average displacement of the entire diaphragm (limit 1.2)")
DRIFT_764_NOTE = "informative (not the IS 1893 criterion): deviation from the chord / average storey drift"


def _flexible_764(lateral, d, k):
    """X01: the HR flexible-diaphragm run's IS 1893 7.6.4 record of storey k, direction d -- 'ratio' = in-plane
    deviation from the chord / average displacement of the entire diaphragm (7.6.4 literal, GOLD-764); the deviation /
    average storey drift is kept as an informative ratio.  Older HR records ('ratio' drift-based, the literal value in
    'ratio_vs_avg_displacement') are read through their literal field.  None when the HR run did not perform the
    Table 5(ii) analysis."""
    lv = ((((lateral or {}).get("diaphragm_7_6_4") or {}).get("flexible_run") or {}).get("levels") or {}).get(d) or []
    for r in lv:
        if isinstance(r, dict) and int(r.get("level", -1)) == int(k):
            lit = r.get("ratio_vs_avg_displacement")
            if not isinstance(lit, (int, float)):
                lit = r.get("ratio") if (r.get("ratio_basis") or "avg_storey_drift_mm" not in r) else None
            drift = r.get("ratio_vs_storey_drift")
            if drift is None and not r.get("ratio_basis") and "avg_storey_drift_mm" in r:
                drift = r.get("ratio")                  # older record: 'ratio' was the drift-based value
            lim = r.get("limit") or 1.2
            out = {q: r.get(q) for q in ("delta_max_from_chord_mm", "delta_avg_diaphragm_mm", "avg_storey_drift_mm",
                                         "limit")}
            out.update(ratio=lit, ratio_basis=RATIO_764_NOTE, ratio_vs_storey_drift=drift,
                       ratio_vs_storey_drift_note=DRIFT_764_NOTE,
                       classification=(("flexible" if lit > lim else "rigid") if isinstance(lit, (int, float))
                                       else r.get("classification")))
            return out
    return None




# ---------------------------------------------------------------------------------------------------------------------
# H3 (audit round 5): the diaphragm demand comes from the ANALYSED line reactions of the HR sub-run, divided by the deck
# length actually present along each line -- never from an equal share F / n spread over the plan depth.
# ---------------------------------------------------------------------------------------------------------------------
H3_CLAUSE = ("diaphragm unit shear per frame line = analysed line reaction / deck length present along the line at the "
             "level (IS 1893 (Part 1):2016 7.6.3 storey forces at gamma 1.0, 7.6.4 rigid / flexible diaphragm; IS 875-3 "
             "storey wind); enveloped over the rigid-diaphragm load path of the analysed model and the flexible-diaphragm "
             "(tributary) line shears where the Table 5(ii) run or a flexible label applies, EQ and W")
RIGID_BASIS = ("HR package collectors.rows: rigid-diaphragm load path by equilibrium of the analysed model "
               "(india_diaphragm, R_line = sum of the vertical-element deliveries of the line)")
FLEX_ROWS_BASIS = "HR package collectors.rows: flexible-diaphragm tributary line shears (IS 1893 7.6.4)"
TRIB_BASIS = {"EQ": ("flexible-diaphragm line shears (IS 1893 7.6.4): storey force with the deck area of the level, carried "
                     "to the frame lines as simple spans between them (the X01 deck-model line reactions are not recorded "
                     "in the HR package)"),
              "W": ("flexible-diaphragm line shears (IS 1893 7.6.4): storey wind by tributary width over the level's "
                    "extent (the HR rule india_diaphragm.tributary_line_shears)")}
LINE_TOL_MM = 5.0


def _hr_collector_rows(lateral):
    """(rows, source, error): the HR sub-run's collectors.rows (lateral_result 'collectors', else the sub-run
    calc_package.json).  error is set when the package records no line reactions or the HR collector analysis failed."""
    lateral = lateral or {}
    col, src = lateral.get("collectors"), "lateral_result.json collectors"
    if not isinstance(col, dict) or col.get("rows") is None:
        root = lateral.get("root")
        pth = os.path.join(root, "design", "calc_package.json") if root else None
        if pth and os.path.exists(pth):
            try:
                col, src = json.load(open(pth)).get("collectors"), "design/calc_package.json collectors"
            except (OSError, ValueError) as ex:
                return None, None, "the HR calc_package.json is unreadable (%s)" % ex
    if not isinstance(col, dict) or col.get("rows") is None:
        return None, None, "the HR lateral package records no line reactions (collectors.rows missing)"
    if col.get("error"):
        return None, src, "the HR collector / line-reaction analysis failed: %s" % col["error"]
    rows = [r for r in (col.get("rows") or []) if isinstance(r, dict)]
    errs = [r["error"] for r in rows if r.get("error")]
    if errs:
        return None, src, "the HR collector / line-reaction analysis failed: %s" % errs[0]
    return rows, src, None


def _reaction_sets(rows):
    """{(kind, source): {(k, d): {line_mm: {R_N, q_N_per_mm, upper_bound}}}} and the HR chord maxima {(kind, k, d): N}.
    source 'rigid' = the rigid load path (incl. the rigid half of an X01 envelope), 'flexible' = tributary rows."""
    sets, chords = {}, {}
    for r in rows:
        kind, d, k = r.get("kind"), r.get("dir"), r.get("level")
        if kind not in ("EQ", "W") or d not in ("X", "Y") or k is None:
            continue
        k = int(k)
        if r.get("role") == "collector" and r.get("R_line_N") is not None and r.get("line") is not None:
            txt = "%s %s" % (r.get("cite") or "", r.get("basis") or "")
            src = "flexible" if (not r.get("case") and (r.get("upper_bound") or r.get("vertical_elements") is not None
                                                        or "tributary" in txt)) else "rigid"
            ln = sets.setdefault((kind, src), {}).setdefault((k, d), {})
            key = float(r["line"])
            for kk in ln:
                if abs(kk - key) <= LINE_TOL_MM:
                    key = kk
                    break
            R = float(r["R_line_N"])
            old = ln.get(key)
            if old is None or abs(R) > abs(old["R_N"]):
                ln[key] = {"R_N": R, "q_N_per_mm": r.get("q_N_per_mm"), "upper_bound": bool(r.get("upper_bound"))}
        elif r.get("role") == "chord" and r.get("N_N") is not None:
            chords[(kind, k, d)] = max(chords.get((kind, k, d), 0.0), abs(float(r["N_N"])))
    return sets, chords


def _lvl_sets(v, NF):
    """{level | 'a-b' | 'default': [[i, j], ...]} -> {k: {(i, j)}} (a missing level -> empty)."""
    out = {k: set() for k in range(1, NF + 1)}
    for key, pts in dict(v or {}).items():
        a_, _, b_ = str(key).partition("-")
        try:
            ks = range(int(a_), int(b_ or a_) + 1)
        except ValueError:
            continue
        for k in ks:
            if k in out:
                out[k] |= {tuple(int(x) for x in p) for p in (pts or [])}
    return out


def _frame_geometry(cfg, lateral):
    """The analysed frame's plan geometry per level: grid coordinates (mm), the level's diaphragm nodes (present set of
    the HR sub-run model -- design/cfg_snapshot.json -- less the declared free nodes and stepped (grade) bases) and the
    deck cells (four corners in the diaphragm, less the declared void cells of diaphragm_stiffness).  'known' is False
    when a job-local builder ran and its footprint cannot be read back."""
    geo = cfg["geometry"]; lf = cfg.get("lateral_frame") or {}
    NF = len(list(geo["heights_m"]))
    g = (lf.get("gold") or {}) if lf.get("custom_build_module") else {}
    snap = None
    root = (lateral or {}).get("root")
    if root and os.path.exists(os.path.join(root, "design", "cfg_snapshot.json")):
        try:
            snap = json.load(open(os.path.join(root, "design", "cfg_snapshot.json")))
        except (OSError, ValueError):
            snap = None
    out = {"known": True, "notes": []}
    if isinstance(snap, dict) and snap.get("NX") is not None and str(snap.get("units") or "N-mm") == "N-mm":
        NX, NY = int(snap["NX"]), int(snap["NY"])
        xc = [float(x) for x in (snap.get("xcoords") or [i * float(snap["SX"]) for i in range(NX + 1)])]
        yc = [float(y) for y in (snap.get("ycoords") or [j * float(snap["SY"]) for j in range(NY + 1)])]
        pres = snap.get("present") or {}
        full = {(i, j) for i in range(NX + 1) for j in range(NY + 1)}
        present = {}
        for k in range(1, NF + 1):
            P = pres.get(str(k), pres.get(k)) if isinstance(pres, dict) else None
            present[k] = {tuple(p) for p in P} if P else set(full)
        if float(snap.get("skew") or 0.0):
            out["known"] = False
            out["notes"].append("skewed grid: the deck length along a line is not read from the model")
        out["source"] = "HR sub-run model (design/cfg_snapshot.json: present / xcoords / ycoords)"
    else:
        NX, NY = int(lf["NX"]), int(lf["NY"])
        bxm = float(lf.get("bay_x_m") or float(geo["plan_x_m"]) / max(NX, 1))
        bym = float(lf.get("bay_y_m") or float(geo["plan_y_m"]) / max(NY, 1))
        xc = [float(x) * 1000.0 for x in (g.get("xcoords_m") or [i * bxm for i in range(NX + 1)])]
        yc = [float(y) * 1000.0 for y in (g.get("ycoords_m") or [j * bym for j in range(NY + 1)])]
        if g:
            import india_cfs_frame_build as FBW
            pf = FBW.make_gold({"NX": NX, "NY": NY, "heights_m": list(geo["heights_m"]), "gold": g})["present"]
            present = {k: set(pf(k)) for k in range(1, NF + 1)}
            out["source"] = "CFS cfg lateral_frame.gold (present per level)"
        else:
            present = {k: {(i, j) for i in range(NX + 1) for j in range(NY + 1)} for k in range(1, NF + 1)}
            out["source"] = "CFS cfg regular grid NX x NY"
            if lf.get("custom_build_module"):
                out["known"] = False
                out["notes"].append("job-local builder without a readable HR model snapshot: deck lengths unknown")
    free, stepped = _lvl_sets(g.get("free_nodes"), NF), _lvl_sets(g.get("stepped_bases"), NF)
    voids = {k: set() for k in range(1, NF + 1)}
    if lf.get("diaphragm_stiffness"):
        try:
            import india_flexible_diaphragm as FD
            st_, err = FD.diaphragm_stiffness({"diaphragm_stiffness": lf["diaphragm_stiffness"], "heights": list(geo["heights_m"])})
            for k, v in ((st_ or {}).get("void_cells") or {}).items():
                if int(k) in voids:
                    voids[int(k)] |= {tuple(int(a) for a in p) for p in v}
        except Exception as ex:                                    # pragma: no cover - vendored engine missing
            out["notes"].append("diaphragm_stiffness.void_cells not read (%s)" % ex)
    dia, cells = {}, {}
    for k in range(1, NF + 1):
        D = present[k] - free[k] - stepped[k]
        dia[k] = D
        cells[k] = {(i, j) for i in range(NX) for j in range(NY)
                    if {(i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)} <= D and (i, j) not in voids[k]}
    out.update(NX=NX, NY=NY, xc=xc, yc=yc, dia=dia, cells=cells)
    return out


def _line_deck(gm, k, d, pos_mm):
    """Deck present along the line at coordinate pos_mm (normal to the force d) at level k: {grid, on_diaphragm,
    deck_m, node_extent_m}.  A line along X (d = X) is the grid line y = pos; its deck length = the grid segments with a
    deck cell on either side."""
    coords = gm["yc"] if d == "X" else gm["xc"]
    idx = [q for q, c in enumerate(coords) if abs(c - pos_mm) <= LINE_TOL_MM]
    if not idx:
        return {"grid": False, "on_diaphragm": None, "deck_m": None, "node_extent_m": None}
    q = idx[0]
    D, C = gm["dia"].get(k, set()), gm["cells"].get(k, set())
    along = gm["xc"] if d == "X" else gm["yc"]
    nodes = [along[p] for p in range(len(along)) if ((p, q) if d == "X" else (q, p)) in D]
    L = 0.0
    for p in range(len(along) - 1):
        a_, b_ = ((p, q), (p, q - 1)) if d == "X" else ((q, p), (q - 1, p))
        if a_ in C or b_ in C:
            L += abs(along[p + 1] - along[p])
    return {"grid": True, "on_diaphragm": bool(nodes), "deck_m": L / 1000.0,
            "node_extent_m": ((max(nodes) - min(nodes)) / 1000.0) if nodes else 0.0}


def _declared_line_length(geo, k, d, pos_m):
    """geometry.diaphragm_line_length_m {level | 'a-b' | 'default': {'<d>@<coord m>': m | '<d>': {coord m: m}}} -> (m, key)
    or (None, None).  The direction is always named (a bare coordinate is ambiguous at a corner)."""
    lv = _per_storey(geo.get("diaphragm_line_length_m"), k)
    if not isinstance(lv, dict):
        return None, None
    cands = list((lv.get(d) or {}).items()) if isinstance(lv.get(d), dict) else []
    for key, val in lv.items():
        s_ = str(key).strip().upper()
        if s_[:2] == d + "@":
            cands.append((s_[2:], val))
    for key, val in cands:
        try:
            if abs(float(key) - pos_m) <= 0.05:
                return float(val), "%s@%s" % (d, key)
        except (TypeError, ValueError):
            continue
    return None, None


def _diaphragm_labels(lf, NF):
    """{k: 'rigid' | 'flexible'} from lateral_frame.diaphragm / diaphragm_by_level (the HR diaphragm_labels rule)."""
    base = str(lf.get("diaphragm") or "rigid").lower()
    bl = lf.get("diaphragm_by_level") if isinstance(lf.get("diaphragm_by_level"), dict) else {}
    lab = {k: str(bl.get("default") or base).lower() for k in range(1, NF + 1)}
    for key, v in bl.items():
        if key == "default":
            continue
        a_, _, b_ = str(key).partition("-")
        try:
            for k in range(int(a_), int(b_ or a_) + 1):
                if k in lab:
                    lab[k] = str(v).lower()
        except ValueError:
            continue
    return lab


def _lateral_line_coords(cfg, gm, d, k, NF):
    """Coordinates (mm, normal to d) of the frame lines that deliver to level k: braced bays (lateral_frame.braced_bays,
    gold xbays / ebf_bays of storey k or k + 1) and moment lines."""
    lf = cfg.get("lateral_frame") or {}
    g = (lf.get("gold") or {}) if lf.get("custom_build_module") else {}
    NX, NY = gm["NX"], gm["NY"]
    bays = lf.get("braced_bays", "perimeter")
    if bays == "perimeter":
        bays = [["X", i, 0] for i in range(NX)] + [["X", i, NY] for i in range(NX)] + \
               [["Y", 0, j] for j in range(NY)] + [["Y", NX, j] for j in range(NY)]
    elif bays == "core":
        bays = [["X", NX // 2, NY // 2], ["Y", NX // 2, NY // 2]]
    bays = list(bays) if isinstance(bays, (list, tuple)) else []
    if g:
        import india_cfs_frame_build as FBW
        for key in ("xbays", "ebf_bays"):
            for s_ in (k, k + 1):
                if s_ <= NF:
                    bays += list(FBW._rng_pick(g.get(key), s_) or [])
    idx = {int(b[2]) if d == "X" else int(b[1]) for b in bays if b and b[0] == d}
    idx |= {int(m[1]) for m in list(lf.get("moment_lines") or []) + list(g.get("moment_lines") or []) if m and m[0] == d}
    coords = gm["yc"] if d == "X" else gm["xc"]
    return sorted(coords[q] for q in idx if 0 <= q < len(coords))


def _tributary(F_N, lines_mm, ext_mm):
    """IS 1893 7.6.4 flexible diaphragm, wind: the storey force to the lines by tributary width over the level's extent
    (uniform along the facade width; the HR rule india_diaphragm.tributary_line_shears, e = 0).  {pos: |V| N}."""
    x0, x1 = ext_mm
    b = x1 - x0
    pos = sorted(lines_mm)
    out = {}
    if not pos or b <= 0:
        return out
    for i, p in enumerate(pos):
        lo = x0 if i == 0 else 0.5 * (pos[i - 1] + p)
        hi = x1 if i == len(pos) - 1 else 0.5 * (p + pos[i + 1])
        out[p] = abs(F_N) * max(min(hi, x1) - max(lo, x0), 0.0) / b
    return out


def _tributary_by_deck(F_N, lines_mm, pieces):
    """IS 1893 7.6.4 flexible diaphragm, seismic: the storey force distributed with the deck area (floor mass, IS 1893
    7.4, uniform over the level's deck cells) and carried to the lines as a chain of simple spans (a deck strip between
    two lines -> lever rule; beyond the outer lines -> the outer line).  pieces [(s_a, s_b, area)] the deck cells
    projected normal to the force (mm).  {pos: |V| N}."""
    pos = sorted(lines_mm)
    A = sum(a for _, _, a in pieces)
    out = {p: 0.0 for p in pos}
    if not pos or A <= 0:
        return out
    for (sa, sb, a) in pieces:
        cuts = sorted({sa, sb} | {p for p in pos if sa < p < sb})
        for u, v in zip(cuts[:-1], cuts[1:]):
            P = abs(F_N) * a / A * (v - u) / (sb - sa)
            c = 0.5 * (u + v)
            if c <= pos[0]:
                out[pos[0]] += P
            elif c >= pos[-1]:
                out[pos[-1]] += P
            else:
                i = max(q for q in range(len(pos)) if pos[q] <= c)
                sp = pos[i + 1] - pos[i]
                out[pos[i]] += P * (pos[i + 1] - c) / sp
                out[pos[i + 1]] += P * (c - pos[i]) / sp
    return out


def _chord_from_reactions(reac, s0, s1, B_m):
    """Chord force (N) of the diaphragm spanning between the lines as a beam loaded by w = sum R / (s1 - s0) and
    supported by the line reactions (the HR rigid chord rule): max |M(s)| / B.  reac [(s_mm, R_N)]."""
    if s1 - s0 <= 0 or not B_m or not reac:
        return 0.0
    w = sum(R for _, R in reac) / (s1 - s0)
    pts = sorted({s0, s1} | {s for s, _ in reac} | {s0 + (s1 - s0) * t / 200.0 for t in range(201)})

    def M(s):
        return w * (s - s0) ** 2 / 2.0 - sum(R * (s - sl) for sl, R in reac if sl < s - 1e-9)
    return max(abs(M(s)) for s in pts if s0 - 1e-9 <= s <= s1 + 1e-9) / (B_m * 1000.0)


def _equal_share_superseded(cfg, k, d, F):
    """The pre-H3 value F / (n B) (equal shares over the plan depth) -- kept for comparison only, never checked."""
    geo = cfg["geometry"]; lf = cfg.get("lateral_frame") or {}
    NX, NY = int(lf["NX"]), int(lf["NY"])
    B = float(_per_storey(geo.get("diaphragm_depth_%s_m" % d), k) or (geo["plan_x_m"] if d == "X" else geo["plan_y_m"]))
    bays = lf.get("braced_bays", "perimeter")
    if bays == "perimeter":
        n_ = 2
    elif bays == "core":
        n_ = 1
    else:
        n_ = len({int(b[2]) if d == "X" else int(b[1]) for b in (bays or []) if b[0] == d})
    n_ = int(_per_storey(geo.get("diaphragm_lines_%s" % d), k) or n_ or 2)
    return {"v_kN_per_m": F / 1e3 / (max(n_, 1) * float(B)), "n_lines": n_, "depth_m": float(B),
            "note": "H3: superseded equal-share value F / (n B) -- informative only, not checked"}


def _capacity(dcap, k, v_unit):
    cap = _per_storey(dcap.get("v_allow_kN_per_m"), k)
    ccite = dcap.get("cite")
    if isinstance(cap, dict):
        ccite = cap.get("cite") or ccite
        cap = cap.get("value")
    rec = {"capacity": None, "capacity_basis": "test", "allowable_increase": 1.0, "dc": None, "ok": None, "found": False}
    if cap:
        inc = float(dcap.get("allowable_increase", 1.0))
        rec = {"capacity": float(cap) * inc, "limit": float(cap) * inc, "capacity_basis": dcap.get("basis", "test"),
               "allowable_increase": inc, "capacity_cite": ccite, "capacity_source": dcap.get("source"), "found": True}
        if v_unit is None:
            rec.update(value=None, dc=None, ok=None)
        else:
            rec.update(value=v_unit, dc=v_unit / (float(cap) * inc), ok=v_unit <= float(cap) * inc)
    return rec


def diaphragm_demands(cfg, lateral):
    """Storey diaphragm demands handed from the CFS floor / roof to the frame lines (H3, audit round 5).

    Per level k and direction d, each frame line's unit shear is v = |R_line| / L_deck: R_line = the analysed line
    reaction of the HR sub-run (collectors.rows of its package: the rigid-diaphragm load path of the analysed model, and
    the flexible-diaphragm tributary rows at flexible-labelled levels), enveloped with the IS 1893 7.6.4 tributary line
    shears where the Table 5(ii) flexible run (X01) ran or the level is labelled flexible, for EQ and W (storey forces
    at gamma 1.0); L_deck = the deck length actually present along the line at that level (the analysed model's deck
    cells -- four corners in the level's diaphragm -- bordering the line), or a declared
    geometry.diaphragm_line_length_m {level: {'<d>@<coord m>': m}} where the model is ambiguous (WARN; a declared length
    longer than the model's deck is not used).  A line with no node in the level's diaphragm (grade / stepped-base /
    free nodes) is not a deck line and is listed apart.  The chord force comes from the same reactions (max |M| / B).
    Fail closed: when the line reactions cannot be found the row is not evaluated (no equal-share value is checked).
    Capacities of a sheathed / decked CFS diaphragm need a cited product / test value -- IS 801 has no diaphragm
    provision (9.1.4) -- so the capacity slot is found:false until the EOR supplies one; the declared allowable_increase
    (IS 801 6.1.2 4/3 only on an IS801_allowable basis, consistency rule) is kept.  Collector rows at declared
    re-entrant lines (geometry.reentrant_lines_X / _Y) carry max(F (1 - B_short/B), the analysed collector axial on the
    line)."""
    geo = cfg["geometry"]; H = list(geo["heights_m"]); NF = len(H)
    lf = cfg.get("lateral_frame") or {}
    lat = lateral or {}
    lpp = os.path.join(lat.get("root") or "", "load_plan.json")
    lp = json.load(open(lpp)) if lat.get("root") and os.path.exists(lpp) else {}
    sf = lp.get("story_forces") or {}
    dcap = cfg.get("diaphragm_capacity") or {}
    rows_hr, rows_src, rows_err = _hr_collector_rows(lat)
    sets, hr_chords = _reaction_sets(rows_hr or [])
    gm = _frame_geometry(cfg, lat)
    labels = _diaphragm_labels(lf, NF)
    x01 = bool(((lat.get("seismic_analysis") or {}).get("flexible_diaphragm_run")))
    out = []
    for k in range(1, NF + 1):
        for d in ("X", "Y"):
            di = 0 if d == "X" else 1
            Fk = {kind: abs(float((sf.get("%s_%s" % (kind, d)) or {}).get(str(k), [0, 0, 0])[di])) for kind in ("EQ", "W")}
            gov_kind = "EQ" if Fk["EQ"] >= Fk["W"] else "W"
            D = gm["dia"].get(k, set())
            along = gm["xc"] if d == "X" else gm["yc"]
            normal = gm["yc"] if d == "X" else gm["xc"]
            s_nodes = [normal[j if d == "X" else i] for (i, j) in D]
            a_nodes = [along[i if d == "X" else j] for (i, j) in D]
            ext = (min(s_nodes), max(s_nodes)) if s_nodes else (0.0, 0.0)
            B_model = (max(a_nodes) - min(a_nodes)) / 1000.0 if a_nodes else None
            B_decl = _per_storey(geo.get("diaphragm_depth_%s_m" % d), k)
            B = min(x for x in (B_model, float(B_decl) if B_decl else None) if x) if (B_model or B_decl) else None
            row = {"storey": k, "dir": d, "F_EQ_N": Fk["EQ"], "F_W_N": Fk["W"], "governing": gov_kind, "F_N": Fk[gov_kind],
                   "depth_m": B, "span_m": (ext[1] - ext[0]) / 1000.0, "label": labels.get(k), "clause": H3_CLAUSE,
                   "source": "india_cfs_lateral.diaphragm_demands (H3); line reactions: %s; deck geometry: %s"
                             % (rows_src or "none", gm.get("source")),
                   "note": "diaphragm shear capacity requires a cited test / product value for the deck or sheathing "
                           "(IS 801 9.1.4 excludes diaphragms; no Indian table) -- EOR input",
                   "superseded_equal_share": _equal_share_superseded(cfg, k, d, Fk[gov_kind]), "warnings": []}
            # ---- reaction sets at (k, d) ----
            cases = []                                   # (label, kind, basis, {pos_mm: {R_N, q, upper_bound}})
            for (kind, src), by in sorted(sets.items()):
                if by.get((k, d)):
                    cases.append(("%s %s" % (kind, src), kind, RIGID_BASIS if src == "rigid" else FLEX_ROWS_BASIS, by[(k, d)]))
            trib_kinds = (["EQ"] if x01 else []) + (["EQ", "W"] if labels.get(k) == "flexible" else [])
            reasons = []
            if rows_err:
                reasons.append(rows_err)
            for kind in sorted(set(trib_kinds)):
                if not Fk[kind]:
                    continue
                lines_t = [p for p in _lateral_line_coords(cfg, gm, d, k, NF)
                           if _line_deck(gm, k, d, p).get("on_diaphragm")]
                if not lines_t or not s_nodes:
                    reasons.append("flexible-diaphragm %s line shears at level %d %s not evaluable: no frame line of the "
                                   "declared braced bays / moment lines lies in the level's diaphragm" % (kind, k, d))
                    continue
                if kind == "EQ":
                    C = gm["cells"].get(k, set())
                    pieces = [(normal[j if d == "X" else i], normal[j + 1 if d == "X" else i + 1],
                               abs(gm["xc"][i + 1] - gm["xc"][i]) * abs(gm["yc"][j + 1] - gm["yc"][j])) for (i, j) in C]
                    tr = _tributary_by_deck(Fk[kind], lines_t, pieces)
                else:
                    tr = _tributary(Fk[kind], lines_t, ext)
                cases.append(("%s flexible tributary" % kind, kind, TRIB_BASIS[kind],
                              {p: {"R_N": V, "q_N_per_mm": None, "upper_bound": False} for p, V in tr.items()}))
            if not rows_err:
                for kind in ("EQ", "W"):
                    if Fk[kind] > 0.0 and not any(c[1] == kind for c in cases):
                        reasons.append("no analysed %s line reactions at level %d %s in the HR package (collectors.rows)"
                                       % (kind, k, d))
            # ---- per line ----
            lines, outside, v_max, gov = [], [], 0.0, None
            pos_all = []
            for c in cases:
                for p in c[3]:
                    if not any(abs(p - q) <= LINE_TOL_MM for q in pos_all):
                        pos_all.append(p)
            for p in sorted(pos_all):
                Rs = {}
                ub = False
                ext_hr, ext_tol = 0.0, 0.0
                for (lab, kind, basis, rec) in cases:
                    for q, rr in rec.items():
                        if abs(q - p) <= LINE_TOL_MM:
                            Rs[lab] = rr["R_N"]
                            ub = ub or rr.get("upper_bound")
                            qq = abs(float(rr.get("q_N_per_mm") or 0.0))
                            if qq >= 1e-3:              # the HR line length R / q (q is rounded to 1e-4 N/mm)
                                e_ = abs(rr["R_N"]) / qq / 1000.0
                                if e_ > ext_hr:
                                    ext_hr, ext_tol = e_, e_ * 5e-5 / qq
                Rmax = max(abs(v) for v in Rs.values()) if Rs else 0.0
                info = _line_deck(gm, k, d, p)
                lrec = {"line_m": round(p / 1000.0, 3), "R_kN": {lab: round(v / 1e3, 3) for lab, v in Rs.items()},
                      "deck_length_model_m": info["deck_m"], "line_node_extent_m": info["node_extent_m"]}
                if info["grid"] and info["on_diaphragm"] is False:
                    lrec["reason"] = ("no node of this line is in the level-%d diaphragm (grade / stepped-base / free nodes): "
                                    "the reaction is delivered to those nodes, not through the deck" % k)
                    outside.append(lrec)
                    continue
                L = info["deck_m"] if (gm["known"] and info["grid"] and info["deck_m"]) else None
                decl, dkey = _declared_line_length(geo, k, d, p / 1000.0)
                if decl is not None:
                    if L is None:
                        L = decl
                        lrec["deck_length_basis"] = "declared geometry.diaphragm_line_length_m[%s]" % dkey
                        row["warnings"].append("diaphragm level %d %s line %.3f m: deck length %.2f m DECLARED "
                                               "(geometry.diaphragm_line_length_m), not read from the model -- VERIFY"
                                               % (k, d, p / 1000.0, decl))
                    elif decl < L - 1e-6:
                        lrec["deck_length_basis"] = ("declared geometry.diaphragm_line_length_m[%s] (shorter than the "
                                                   "model's %.2f m)" % (dkey, L))
                        row["warnings"].append("diaphragm level %d %s line %.3f m: declared deck length %.2f m used "
                                               "(model %.2f m) -- VERIFY" % (k, d, p / 1000.0, decl, L))
                        L = decl
                    else:
                        row["warnings"].append("diaphragm level %d %s line %.3f m: declared deck length %.2f m exceeds "
                                               "the model's deck %.2f m -- not used" % (k, d, p / 1000.0, decl, L))
                if not L:
                    why = ("the line is off the model grid" if not info["grid"] else
                           "no deck cell borders the line in the model" if gm["known"] else "; ".join(gm["notes"]))
                    lrec["reason"] = ("deck length along the line not determinable (%s): declare "
                                    "geometry.diaphragm_line_length_m {%d: {'%s@%.3f': m}}" % (why, k, d, p / 1000.0))
                    lines.append(lrec)
                    reasons.append("level %d %s line %.3f m (R %.1f kN): %s" % (k, d, p / 1000.0, Rmax / 1e3, lrec["reason"]))
                    continue
                lrec.setdefault("deck_length_basis", "model deck cells bordering the line (%s)" % gm.get("source"))
                lrec["deck_length_m"] = L
                vv = {lab: abs(v) / 1e3 / L for lab, v in Rs.items()}
                lab_g = max(vv, key=vv.get) if vv else None
                lrec.update(v_kN_per_m=vv.get(lab_g, 0.0), governing_case=lab_g)
                if ub or (ext_hr and info["node_extent_m"] is not None
                          and ext_hr > 1.01 * info["node_extent_m"] + 0.1 + ext_tol):
                    lrec["upper_bound"] = ("the analysed line extends %.2f m beyond the level's diaphragm nodes (%.2f m): "
                                         "R includes deliveries at nodes outside the deck and is taken whole on the deck "
                                         "length (upper bound)" % (ext_hr, info["node_extent_m"] or 0.0)) if not ub else \
                        "HR tributary row flagged upper bound"
                lines.append(lrec)
                if lrec["v_kN_per_m"] > v_max:
                    v_max, gov = lrec["v_kN_per_m"], lrec
            # ---- chord from the same reactions ----
            chord = 0.0
            for (lab, kind, basis, rec) in cases:
                reac = [(q, rr["R_N"]) for q, rr in rec.items()
                        if _line_deck(gm, k, d, q).get("on_diaphragm") is not False]
                chord = max(chord, _chord_from_reactions(reac, ext[0], ext[1], B))
            for kind in ("EQ", "W"):
                chord = max(chord, hr_chords.get((kind, k, d), 0.0))
            evaluated = not reasons
            if not cases and not Fk["EQ"] and not Fk["W"]:
                evaluated, v_max = True, 0.0
                row["note_demand"] = "no storey force at this level / direction"
            v_unit = v_max if evaluated else None
            row.update(v_unit_kN_per_m=v_unit, chord_force_kN=chord / 1e3, n_lines=sum(1 for x in lines if "deck_length_m" in x),
                       lines=lines, lines_outside_deck=outside, cases=[{"case": c[0], "basis": c[2]} for c in cases],
                       demand_evaluated=evaluated, **_capacity(dcap, k, v_unit))
            if gov:
                row.update(governing=gov["governing_case"].split()[0], governing_case=gov["governing_case"],
                           governing_line_m=gov["line_m"], governing_R_kN=max(abs(x) for x in gov["R_kN"].values()),
                           governing_deck_length_m=gov["deck_length_m"], F_N=Fk[gov["governing_case"].split()[0]])
            if not evaluated:
                row.update(ok=None, dc=None, found=False,
                           note="diaphragm demand not evaluated (fail closed, H3): " + "; ".join(reasons),
                           v_evaluated_lines_max_kN_per_m=v_max if lines else None)
            fr = _flexible_764(lateral, d, k)
            if fr:
                row["flexible_run_7_6_4"] = fr          # X01: in-plane deformation measured on the HR flexible run
            out.append(row)
            # ---- C03 / CFS-C-17: collectors (drag struts) at declared re-entrant lines ----
            Fg = Fk[gov_kind]
            for rl in (geo.get("reentrant_lines_%s" % d) or []):
                st_ = rl.get("storeys") or rl.get("storey")
                if st_ not in (None, "all"):
                    sts = st_ if isinstance(st_, (list, tuple)) else [st_]
                    if k not in [int(x) for x in sts]:
                        continue
                Bs = float(rl["B_short_m"]); Bf = float(rl.get("B_m") or B or (geo["plan_x_m"] if d == "X" else geo["plan_y_m"]))
                Ff = Fg * max(0.0, 1.0 - Bs / Bf)
                pos_m = rl.get("coord_m")
                if pos_m is None:
                    import re
                    mm_ = re.search(r"-?\d+(?:\.\d+)?", str(rl.get("line") or ""))
                    pos_m = float(mm_.group(0)) if mm_ else None
                Na = 0.0
                if pos_m is not None:
                    for r in rows_hr or []:
                        if (r.get("role") == "collector" and r.get("dir") == d and int(r.get("level") or -1) == k
                                and r.get("line") is not None and abs(float(r["line"]) - float(pos_m) * 1000.0) <= LINE_TOL_MM):
                            Na = max(Na, abs(float(r.get("N_N") or 0.0)))
                Fc = max(Ff, Na)
                crow = {"storey": k, "dir": d, "kind": "collector", "line": rl.get("line"), "F_N": Fg, "B_short_m": Bs, "B_m": Bf,
                        "value": Fc / 1e3, "F_collector_kN": Fc / 1e3, "F_collector_formula_kN": Ff / 1e3,
                        "N_collector_analysed_kN": (Na / 1e3) if pos_m is not None else None, "demand_level": "working",
                        "clause": "re-entrant corner collector (drag strut): max of F (1 - B_short/B) of the storey force and "
                                  "the analysed collector axial on the line (HR collectors.rows, the same line reactions as the "
                                  "diaphragm rows) (IS 1893 7.6.3 storey force / IS 875-3 storey wind)",
                        "limit": None, "dc": None, "ok": None, "found": False, "capacity_basis": rl.get("capacity_basis", "EOR_input"),
                        "allowable_increase": 1.0,
                        "note": "collector capacity: declare reentrant_lines_%s[].capacity_kN + cite (working-stress capacity of the "
                                "drag member / its connections)" % d}
                if rl.get("capacity_kN"):
                    capk = float(rl["capacity_kN"])
                    crow.update(limit=capk, capacity=capk, dc=(Fc / 1e3) / capk, ok=(Fc / 1e3) <= capk + 1e-9, found=True,
                                capacity_cite=rl.get("cite"), note=None)
                out.append(crow)
    return out
