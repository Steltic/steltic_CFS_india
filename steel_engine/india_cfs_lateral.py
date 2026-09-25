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


def resolve_system(zone, system=None, height_m=None):
    """Return (system, R, cite) for a CFS building's hot-rolled frame in a zone; refuse banned combinations."""
    zone = str(zone).upper()
    if zone not in SYSTEM_BY_ZONE:
        raise LateralSystemError("zone %r not in II-V" % zone)
    sysn = (system or SYSTEM_BY_ZONE[zone][0]).upper()
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
    return sysn, TABLE9_R[sysn], TABLE9_CITE


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
           "k4": k4, "Kd": Kd, "Kc": Kc, "cyclone_belt": bool(cb), "cyclone_belt_cite": site.get("cyclone_belt_cite"),
           "terrain_category": site.get("terrain_category"), "Ka_basis": "frame_tributary", "storeys": []}
    hs = []
    z = 0.0
    for h in H:
        z += h; hs.append(z)
    # frame tributary area for Ka (7.2.2.1 (a)): frame spacing x storey height
    lf = cfg.get("lateral_frame") or {}
    sp = max(float(lf.get("bay_x_m", Lx)), float(lf.get("bay_y_m", Ly)))
    Ka_rec = WT.resolve_ka(sp * max(H), site.get("Ka_corpus_hit"))
    if not Ka_rec.get("found"):
        raise LateralSystemError("Ka (Table 4) unresolved: %s" % Ka_rec.get("cite"))
    Ka = float(Ka_rec["Ka"])
    out.update(Ka=Ka, Ka_area_m2=sp * max(H), Ka_cite=Ka_rec.get("cite"))
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
        for k, h in enumerate(H, start=1):
            roof = k == len(H)
            ztop = hs[k - 1]
            k2 = _k2(site, ztop)
            Vz = Vb * k1 * k2 * k3 * k4
            pz = 0.6 * Vz ** 2 / 1000.0            # kN/m2
            pd = max(Kd * Ka * Kc * pz, 0.70 * pz)
            trib = H[k - 1] / 2.0 + (H[k] / 2.0 if k < len(H) else 0.0)     # half storey below + half above
            F = net * pd * B * trib * 1000.0      # N
            forces["W_" + d][str(k)] = [F if d == "X" else 0.0, F if d == "Y" else 0.0, 0.0]
            if d == "X":
                out["storeys"].append({"k": k, "z_m": ztop, "k2": round(k2, 4), "Vz_mps": round(Vz, 3), "pz_kNm2": round(pz, 4),
                                       "pd_kNm2": round(pd, 4), "trib_h_m": trib})
    out["pz_kNm2"] = max(s["pz_kNm2"] for s in out["storeys"]); out["pd_kNm2"] = max(s["pd_kNm2"] for s in out["storeys"])
    out["VB_x_kN"] = sum(v[0] for v in forces["W_X"].values()) / 1e3
    out["VB_y_kN"] = sum(v[1] for v in forces["W_Y"].values()) / 1e3
    out["cite"] = ("IS 875-3 6.2 Vb (Annex A); 6.3 Vz = Vb k1 k2 k3 k4; Table 2 k2; 6.3.4 k4; 7.2 pz = 0.6 Vz^2, pd = Kd Ka Kc pz "
                   ">= 0.7 pz; 7.2.1 Kd; Table 4 Ka (frame tributary); Table 5 Cpe; 7.3.2 Cpi cancels for the overall shear")
    return out, forces


def build_hr_spec(cfg, name):
    """Declarative HR-frame spec (JSON) from the CFS cfg."""
    lf = cfg["lateral_frame"]; site = cfg["site"]; geo = cfg["geometry"]; ld = cfg["loads"]
    H = list(geo["heights_m"])
    sysn, R, cite = resolve_system(site["zone"], lf.get("system"), sum(H))
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
    if sysn in ("SMF", "SMRF"):
        bays = []
    ws, forces = wind_story_forces(cfg)
    plan = dict(cfg.get("load_plan") or {})
    plan["jurisdiction"] = "india"
    plan["wind_summary"] = dict(plan.get("wind_summary") or {}, **ws)
    plan["gravity_summary"] = dict(plan.get("gravity_summary") or {},
                                   D_floor_kNm2=ld["D_floor"], D_roof_kNm2=ld["D_roof"], L_floor_kNm2=ld["L_floor"],
                                   L_roof_kNm2=ld["Lr"], clad_kNm2=ld.get("clad", 0.0),
                                   partition_kNm2=ld.get("partition_design_kNm2", 0.0), snow_kNm2=ld.get("snow", 0.0))
    plan["story_forces"] = dict(plan.get("story_forces") or {}, **forces)
    plan["story_forces_units"] = "N"
    plan["seismic_summary"] = dict(plan.get("seismic_summary") or {}, code=IS.IS1893_EDITION if hasattr(IS, "IS1893_EDITION") else "IS 1893 (Part 1):2016",
                                   site=site.get("city"), zone=site["zone"], Z=site["Z"], I=I_rec["I"], I_cite=I_rec.get("cite"),
                                   I_row=I_rec.get("row"), R=R, R_cite=cite, system=sysn, soil=site["soil"])
    plan["combinations"] = "auto"
    plan["lateral_frame_basis"] = "IS800_LSD"
    plan.pop("cfs_combinations", None)                      # the HR run sees only the IS 800 set
    spec = {
        "name": name, "system": sysn, "R": R, "Z": site["Z"], "I": I_rec["I"], "zone": site["zone"], "soil": site["soil"],
        "NX": NX, "NY": NY, "bay_x_m": float(lf["bay_x_m"]), "bay_y_m": float(lf["bay_y_m"]), "heights_m": H,
        "D_floor": ld["D_floor"], "D_roof": ld["D_roof"], "L_floor": ld["L_floor"], "Lr": ld["Lr"], "clad": ld.get("clad", 0.0),
        "snow": ld.get("snow", 0.0), "partition_design_kNm2": ld.get("partition_design_kNm2", 0.0),
        "partition_seismic_kNm2": ld.get("partition_seismic_kNm2", 0.5), "partitions": ld.get("partitions", True),
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
        "d_x_m": lf.get("d_x_m"), "d_y_m": lf.get("d_y_m"), "default_strong": lf.get("default_strong"),
        "hr_cfg_extra": lf.get("hr_cfg_extra") or {},       # declared HR cfg keys passed through verbatim (e.g. is18168_table2,
                                                            # grade_by_section, custom_sections, column_imposed_load_reduction)
        "notes": "%s: hot-rolled %s lateral frame (R %s) of a CFS building; CFS members gravity / wind only (D3)"
                 % (name, sysn, R),
    }
    return spec


def run_lateral(cfg, job_dir, name=None, timeout_s=3600):
    """Build the HR spec, run the vendored HR pipeline in a subprocess and return the lateral result summary."""
    name = name or (cfg.get("name") or "job") + "_lateral"
    os.makedirs(job_dir, exist_ok=True)
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


def diaphragm_demands(cfg, lateral):
    """Storey diaphragm demands handed from the CFS floor / roof to the frame lines (IS 1893 7.6.3 storey forces at
    gamma 1.0, IS 875-3 wind storey forces): unit shear into the two frame lines of each direction and the chord
    force M/depth.  Capacities of a sheathed / decked CFS diaphragm need a cited product / test value -- IS 801 has no
    diaphragm provision (9.1.4) -- so each capacity slot is found:false until the EOR supplies one."""
    geo = cfg["geometry"]; H = list(geo["heights_m"])
    Lx, Ly = float(geo["plan_x_m"]), float(geo["plan_y_m"])
    plan = (lateral.get("esm") or {}); sf_eq = (plan.get("story_forces") or {})
    lp = json.load(open(os.path.join(lateral["root"], "load_plan.json"))) if os.path.exists(os.path.join(lateral["root"], "load_plan.json")) else {}
    sf = lp.get("story_forces") or {}
    lf = cfg.get("lateral_frame") or {}
    NX, NY = int(lf["NX"]), int(lf["NY"])
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
    rows = []
    for k in range(1, len(H) + 1):
        # storey force along X is resisted by the frame lines that run along X (y = const, length Lx = the diaphragm
        # depth B); with n equal lines at spacing s = Lspan / (n - 1) the rigid diaphragm hands F / n to each line:
        # v = F / (n B); chord = w s^2 / (8 B) with w = F / Lspan (continuous-diaphragm approximation; n = 2 is the
        # simple span F / (2 B), F Lspan / (8 B)).  WP6-fix: B and Lspan were swapped (B = Ly for X), which under-stated
        # v for the long direction of a rectangle; the line count was ignored.
        for d, B, Lspan in (("X", Lx, Ly), ("Y", Ly, Lx)):
            # non-rectangular plans: depth (line length) and span declared per direction
            B = float(geo.get("diaphragm_depth_%s_m" % d) or B)
            Lspan = float(geo.get("diaphragm_span_%s_m" % d) or Lspan)
            nlines = max(2, int(geo.get("diaphragm_lines_%s" % d) or len(lines[d]) or 2))
            s_span = Lspan / (nlines - 1)
            Fe = abs(float((sf.get("EQ_" + d) or {}).get(str(k), [0, 0, 0])[0 if d == "X" else 1]))
            Fw = abs(float((sf.get("W_" + d) or {}).get(str(k), [0, 0, 0])[0 if d == "X" else 1]))
            F = max(Fe, Fw); gov = "EQ" if Fe >= Fw else "W"
            # flexible-diaphragm tributary share to the two extreme frame lines (perimeter braced bays) or equal split
            v_unit = F / 1e3 / (nlines * B)   # kN/m along each of the n frame lines (length B = diaphragm depth)
            M = (F / Lspan) * s_span ** 2 / 8.0   # N-m: diaphragm panel of span s between adjacent lines
            chord = M / B                     # N
            dcap = cfg.get("diaphragm_capacity") or {}
            cap = dcap.get("v_allow_kN_per_m")
            rec_cap = {"capacity": None, "capacity_basis": "test", "allowable_increase": 1.0, "dc": None, "ok": None, "found": False}
            if cap:
                inc = float(dcap.get("allowable_increase", 1.0))
                rec_cap = {"capacity": float(cap) * inc, "value": v_unit, "limit": float(cap) * inc, "capacity_basis": dcap.get("basis", "test"),
                           "allowable_increase": inc, "dc": v_unit / (float(cap) * inc), "ok": v_unit <= float(cap) * inc, "found": True,
                           "capacity_cite": dcap.get("cite"), "capacity_source": dcap.get("source")}
            rows.append({"storey": k, "dir": d, "F_EQ_N": Fe, "F_W_N": Fw, "governing": gov, "F_N": F, "n_lines": nlines,
                         "v_unit_kN_per_m": v_unit, "chord_force_kN": chord / 1e3, "span_m": Lspan, "panel_span_m": s_span, "depth_m": B, **rec_cap,
                         "clause": "IS 1893 7.6.3 storey force (gamma 1.0) / IS 875-3 storey wind; rigid diaphragm on n equal frame lines: "
                                   "shear = F/(n B) per unit length of line, chord = (F/L) s^2/(8 B), s = L/(n - 1)",
                         "note": "diaphragm shear capacity requires a cited test / product value for the deck or sheathing "
                                 "(IS 801 9.1.4 excludes diaphragms; no Indian table) -- EOR input"})
    return rows
