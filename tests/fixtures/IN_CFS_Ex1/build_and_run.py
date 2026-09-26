#!/usr/bin/env python3
"""IN_CFS_Ex1 -- 4-storey residential CFS building, New Delhi (Zone IV): hot-rolled SCBF (R 4.5) lateral frame +
IS 801 cold-formed studs / joists (decision D3 / D5), wave-2 end-to-end run (CFS implementer).

Design decisions (the 'agent'):
  * Site: New Delhi, IS 1893 Annex E Zone IV Z = 0.24 (rag/IS1893_annexE_zones.json); medium soil (Type II);
    IS 875-3 Annex A Vb = 47 m/s (rag/IS875_P3_annexA_Delhi.json), terrain category 3, Table 2 k2 (rag/IS875_P3_table2_k2.json);
    inland (outside the 60 km cyclone belt, D10): Kd 0.9, k4 1.0.
  * Occupancy: residential 4 x 96 m2 = 384 m2, < 200 persons -> I = 1.0 (IS 1893 Table 8 (iii); D8).
  * Lateral system: hot-rolled SCBF, R 4.5 (IS 1893 Table 9 SBF concentric; Zone IV -> SCBF per L7); IS 18168:2023
    applies in Zone IV (residential).  Grid 2 x 2 bays (6 m x 4 m) of IS 808 WPB columns, NPB grid beams; X-bracing
    in every perimeter bay, braces IS 808 WPB200X200X50.92 E250 B0 (12.8.2.1; plastic section 12.8.2.5), KL/r = 6708/50.7 = 132 < 160.
    IS 18168 5.3 / Table 2 (E250, Ry 1.4: limit = coefficient x eps/sqrt(Ry) = 0.845 x coefficient) sizes the SFRS members:
    lateral columns WPB200X200X61.3 (b/tf 100/15 = 6.67 <= 9.0 x 0.845 = 7.61; the 50.92 section, 8.42, fails),
    X beams NPB300X150X49.32 (b/tf 5.98 <= 7.61, d/tw 278.6/8.0 = 34.8 <= 44.5 x 0.845 = 37.6; NPB300X165X39.88 fails
    8.51 / 50.1), Y beams NPB200X130X31.56 (6.70 / 29.7; NPB200X130X27.37 fails 7.82); braces WPB200X200X50.92 pass the
    brace row (8.42 <= 11.3 x 0.845 = 9.55).  Gravity columns (not SFRS) stay WPB200X200X42.26.
  * CFS: floor joists CLR180X50X20X3.15 at 400 mm spanning 4 m between the grid beams (deck one-way in Y);
    exterior studs CLR100X50X15X2 at 400 mm, 3.0 m storey, sheathed both faces (IS 801 8.1; Kw from the
    sheathing test declared as EOR input), wind + cladding self-weight only (non-load-bearing: joists bear on the
    hot-rolled beams); IS 1079 grade: Fy 240 MPa (IS 801 Table 2: 24 kgf/mm2 -> F = 1450 kgf/cm2).
  * Loads: floor D 1.5 kN/m2 (CFS joists + 18 mm cement board + screed + finishes, IS 875-1) + partitions 1.0
    (IS 875-2 3.1.2) design and in W (IS 1893 7.3.6: max(0.5, design allowance), ruling R1); residential IL 2.0 kN/m2 (IS 875-2 Table 1); roof D 1.0,
    Lr 0.75 (Table 2, access not provided); cladding 0.5 kN/m2 on the perimeter.
"""
from __future__ import annotations
import json
import math
import os
import sys
from pathlib import Path

JOB = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "steel_engine"))
os.environ.setdefault("STEEL_BUILDER_JOBS", str(REPO / "tests" / "_jobs"))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import india_cfs_env  # noqa: E402,F401
import sections as S  # noqa: E402  (vendored IS 808 DB)

NAME = "IN_CFS_Ex1_SCBF_4levels_Delhi"


def k2_table():
    """IS 875-3 Table 2, terrain category 3 (rag/IS875_P3_table2_k2.json, corpus exact_table 2)."""
    return {10: 0.91, 15: 0.97, 20: 1.01, 30: 1.06, 50: 1.12}


def build_cfg():
    H = [3.0, 3.0, 3.0, 3.0]
    Lx, Ly = 12.0, 8.0
    br = S.props("WPB200X200X50.92")
    Lw, tg, fyg, fug = 600.0, 16.0, 250.0, 410.0
    bw = br["bf"] + 2 * Lw * math.tan(math.radians(30))
    connections = {
        "brace_end": {"default": {
            "weld_type": "cjp", "welds": {"cjp": {"t_mm": br["tf"]}, "length_mm": Lw, "fy_MPa": 250.0, "n_sides": 4, "site": False},
            "gusset": {"t_mm": tg, "fy_MPa": fyg, "fu_MPa": fug, "w_start_mm": br["bf"], "L_conn_mm": Lw, "L_unbraced_mm": 300.0,
                       "K": 0.65, "Avg_mm2": 2 * Lw * tg, "Avn_mm2": 2 * Lw * tg, "Atg_mm2": br["bf"] * tg, "Atn_mm2": br["bf"] * tg},
            "An_mm2": br["A"], "moment_capacity_Nmm": (tg * bw ** 2 / 4.0) * fyg / 1.1,
            "moment_capacity_cite": "gusset in-plane plastic moment on the Whitmore width: t bw^2/4 fy/gamma_m0",
            "bolts_and_welds_share": False, "K_basis": "gusset K = 0.65 (compact corner gusset, EOR)"}},
        "beam_shear": {"default": {
            "t_plate_mm": 10.0, "h_plate_mm": 220.0, "fy_plate_MPa": 250.0, "fu_plate_MPa": 410.0, "bolt_type": "HSFG",
            "slip_surface": "clean_mill_scale",
            "bolts": {"n_bolts": 3, "d_mm": 20, "grade": "8.8", "t_mm": 6.0, "fu_plate_MPa": 410.0, "e_mm": 40.0, "p_mm": 70.0,
                      "d0_mm": 22.0, "nn": 1, "ns": 0},
            "block_shear_areas": {"Avg_mm2": (40 + 2 * 70) * 10.0, "Avn_mm2": (40 + 2 * 70 - 2.5 * 22) * 10.0, "Atg_mm2": 40.0 * 10.0,
                                  "Atn_mm2": (40 - 11) * 10.0},
            "cjp": {"t_mm": 10.0, "length_mm": 220.0, "fy_MPa": 250.0, "n_sides": 1, "site": True}, "weld_type": "cjp"},
            # Y beams NPB200X130X31.56: clear web 210 - 2 x 10 = 190 mm -> a 150 mm fin plate with 2 bolts (e 40, p 70, e 40)
            "NPB200X130X31.56": {
                "t_plate_mm": 10.0, "h_plate_mm": 150.0, "fy_plate_MPa": 250.0, "fu_plate_MPa": 410.0, "bolt_type": "HSFG",
                "slip_surface": "clean_mill_scale",
                "bolts": {"n_bolts": 2, "d_mm": 20, "grade": "8.8", "t_mm": 6.0, "fu_plate_MPa": 410.0, "e_mm": 40.0, "p_mm": 70.0,
                          "d0_mm": 22.0, "nn": 1, "ns": 0},
                "block_shear_areas": {"Avg_mm2": (40 + 70) * 10.0, "Avn_mm2": (40 + 70 - 1.5 * 22) * 10.0, "Atg_mm2": 40.0 * 10.0,
                                      "Atn_mm2": (40 - 11) * 10.0},
                "cjp": {"t_mm": 10.0, "length_mm": 150.0, "fy_MPa": 250.0, "n_sides": 1, "site": True}, "weld_type": "cjp"}},
        "column_base": {"default": {
            "B_mm": 650.0, "L_mm": 650.0, "t_plate_mm": 65.0, "fy_plate_MPa": 230.0, "fck_MPa": 30.0, "fixed": True,
            "anchors": {"n_total": 6, "n_tension": 3, "d_mm": 30, "grade": "8.8", "f_mm": 250.0, "pitch_mm": 150.0, "edge_mm": 100.0,
                        "n_per_row": 3, "Anb_mm2": 561.0},
            "Ec_note": "Ec = 5000 sqrt(30) = 27386 MPa (IS 456:2000 6.2.3.1); plate fy 230 (E250, t > 40, IS 2062 Table 3); "
                       "M30 8.8 Anb 561 mm2 (IS 1367 thread stress area)",
            "embedment": {"capacity_N": 3.1416 * 30.0 * 1500.0 * 1.2,   # = 169 646 N per anchor, see formula string
                          "formula": "bond: pi d L_emb tau_bd = pi x 30 mm x 1500 mm x 1.2 MPa (x 1.6 for deformed / 1.0 plain, HD bolt sleeve) "
                                     "-> 169 646 N per anchor; EOR numbers: d 30 (anchor), L_emb 1500 mm, tau_bd 1.2 MPa (M30 concrete, plain bar, "
                                     "IS 456:2000 Table 26.2.1.1 -- not in the corpus), no cone check -- VERIFY",
                          "cite": "EOR -- IS 456:2000 cl. 26.2.1 development length / cone; standard not in corpus -- VERIFY",
                          "source": "EOR -- IS 456:2000 cl. 26.2.1 development length / cone; standard not in corpus -- VERIFY"}}},
        "column_splice": {"default": {"none": True, "note": "columns continuous over 4 storeys (12 m lengths)"}},
    }
    cfg = {
        "name": NAME, "jurisdiction": "india", "units": "m", "design_basis": "IS801_WSM",
        "brief": "IN_CFS_Ex1 4-storey residential CFS building, New Delhi; D3 rewrite: hot-rolled SCBF lateral frame",
        "site": {"city": "New Delhi", "zone": "IV", "Z": 0.24, "soil": "II", "Vb": 47.0, "Vb_source": "IS 875-3 Annex A (Delhi 47 m/s)",
                 "terrain_category": 3, "k1": 1.0, "k3": 1.0, "cyclone_belt": False,
                 "cyclone_belt_cite": "New Delhi is inland, outside the 60 km east-coast / Gujarat belt (IS 875-3 6.3.4); Kd 0.9 (7.2.1)",
                 "Kd": 0.9, "k2_table": k2_table(), "wind_structure_class": "other"},
        "occupancy": {"use": "residential", "area_m2": 4 * Lx * Ly, "persons": 48,
                      "note": "4 flats per floor x 3 persons = 48 < 200 -> Table 8 (iii) I = 1.0"},
        "geometry": {"plan_x_m": Lx, "plan_y_m": Ly, "heights_m": H},
        "loads": {"D_floor": 1.5, "D_roof": 1.0, "L_floor": 2.0, "Lr": 0.75, "clad": 0.5, "partition_design_kNm2": 1.0,
                  "partition_seismic_kNm2": max(0.5, 1.0), "snow": 0.0,   # ruling R1: max(0.5, design allowance) in W
                  "cite": "IS 875-1 Table 1 assembly; IS 875-2 Table 1 residential 2.0 kN/m2, 3.1.2 partitions 1.0; Table 2 roof 0.75; "
                          "IS 1893 7.3.6 partitions in W = max(0.5, 1.0 design allowance) = 1.0 ('the higher values shall be used'), Table 10 25 % of IL"},
        "lateral_frame": {"system": "SCBF", "R": 4.5, "NX": 2, "NY": 2, "bay_x_m": Lx / 2.0, "bay_y_m": Ly / 2.0,
                          "braced_bays": "perimeter", "brace_config": "X", "base": "fixed",
                          "col": "WPB200X200X61.3", "beam": "NPB300X150X49.32", "brace": "WPB200X200X50.92",
                          "col_sec": {"lateral": {"1-4": "WPB200X200X61.3"}, "gravity": {"1-4": "WPB200X200X42.26"}},
                          "beam_sec": {"floor_X": "NPB300X150X49.32", "floor_Y": "NPB200X130X31.56",
                                       "roof_X": "NPB300X150X49.32", "roof_Y": "NPB200X130X31.56"},
                          "LLT_sag_mm": {"floor": 400.0, "roof": 400.0}, "LLT_hog_mm": {"floor": 6000.0, "roof": 6000.0},
                          "steel_grade": "E250 B0", "brace_grade": "E250 B0", "brace_process": None,
                          "deck_span": "Y", "diaphragm": "rigid", "apply_is18168": True, "connections": connections,
                          "diaphragm_7_6_4": {"declared": "rigid", "plan_aspect_ratio": 1.5},
                          "diaphragm_note": "CFS floor: 18 mm cement board on joists at 400 with a continuous strap chord; "
                                            "7.6.4 classification declared rigid by the EOR (deflection ratio < 1.2)"},
        "cfs_members": {
            "Fy_MPa": 240.0, "grade_cite": "IS 1079 St 34 class / IS 801 Table 2 yield 24 kgf/mm2 -> F = 1450 kgf/cm2 (0.60 Fy)",
            "studs": {"section": "CLR100X50X15X2", "spacing_mm": 400.0, "height_mm": 3000.0, "bearing": False,
                      "sheathing": {"both_faces": True, "a_mm": 300.0, "Kw_N_per_mm": 40.0, "fastener_lateral_capacity_N": 600.0,
                                    "fastener_source": "EOR input: 4.2 mm screw in 12 mm cement board, lateral capacity 600 N per attachment "
                                                       "(manufacturer test report, to be filed) -- VERIFY",
                                    "source": "EOR input: 12 mm cement board both faces, screws at 300 mm; Kw = 40 N/mm per side from the sheathing "
                                              "shear test (IS 801 8.1 'as determined from tests') -- VERIFY"},
                      "cladding_kNm2": 0.5},
            "joists": {"section": "CLR180X50X20X3.15", "spacing_mm": 400.0, "span_mm": 4000.0, "bearing_mm": 50.0,
                       "compression_flange_restrained": True, "deflection_limit_ratio": 300, "deflection_cite": "IS 800:2007 Table 6 (read-only retrieval, serviceability_limits_table6): other buildings, floor and roof, elements not susceptible to cracking, span/300"},
        },
        "diaphragm_capacity": {"v_allow_kN_per_m": 6.0, "allowable_increase": 1.0, "basis": "test",
                               "source": "EOR input: 18 mm cement-bonded board on CFS joists at 400 with screws at 150 mm edge / 300 mm field; "
                                         "allowable diaphragm shear 6.0 kN/m from the manufacturer's tested diaphragm table (report to be filed) -- VERIFY",
                               "cite": "IS 801 9.1.4 excludes diaphragms from the IS 801 test route; capacity is a cited product / test value"},
        "eor_inputs": [
            {"item": "SFRS column-base anchorage embedment (concrete bond / cone)", "value": "169 646 N per M30 anchor: pi x 30 x 1500 x 1.2 MPa (L_emb 1500 mm: the 12.12 / IS 18168 9.3 base demand of the WPB200X200X61.3 column, 155 kN per anchor, exceeds the 135.7 kN of a 1200 mm embedment)",
             "source": "EOR -- IS 456:2000 cl. 26.2.1 development length / cone; standard not in corpus -- VERIFY"},
            {"item": "stud sheathing modulus Kw (IS 801 8.1)", "value": "40 N/mm per side (12 mm cement board, screws at 300 mm)",
             "source": "EOR -- sheathing shear test per IS 801 8.1 -- VERIFY"},
            {"item": "sheathing attachment lateral capacity (IS 801 8.1 (d))", "value": "600 N per 4.2 mm screw",
             "source": "EOR -- manufacturer test report -- VERIFY"},
            {"item": "floor / roof diaphragm allowable shear", "value": "6.0 kN/m (18 mm cement-bonded board, screws 150/300)",
             "source": "EOR -- manufacturer tested diaphragm table -- VERIFY (IS 801 9.1.4: no IS route)"},
        ],
        "load_plan": {
            "jurisdiction": "india", "design_basis": "IS801_WSM", "lateral_frame_basis": "IS800_LSD",
            "combinations": "auto", "cfs_combinations": "auto",
            "retrieval": [
                {"stem": "IS_1893_Part_1_2016", "query": "Annex E Delhi zone", "quote": "Delhi IV 0.24", "found": True, "cite": "IS 1893 (Part 1):2016 Annex E: Delhi Zone IV, Z 0.24",
                 "file": "rag/IS1893_annexE_zones.json"},
                {"stem": "IS_1893_Part_1_2016", "query": "Table 9 response reduction factor SBF concentric", "quote": "| ii)(b) | Buildings with special braced frame (SBF) having concentric braces | 4.5 |", "file": "rag/IS1893_table9_SBF.json", "found": True,
                 "cite": "IS 1893 (Part 1):2016 Table 9: buildings with special braced frame (SBF) having concentric braces R 4.5"},
                {"stem": "IS_1893_Part_1_2016", "query": "Table 8 importance factor residential", "quote": "| iii) | All other buildings | 1.0 |", "file": "rag/IS1893_table8_I.json", "found": True,
                 "cite": "IS 1893 (Part 1):2016 Table 8 (iii) all other buildings I 1.0 (< 200 persons)"},
                {"stem": "IS_875_Part_3_2015", "query": "Annex A Delhi basic wind speed", "quote": "| Delhi | 47 |", "found": True, "cite": "IS 875 (Part 3):2015 Annex A Delhi 47 m/s",
                 "file": "rag/IS875_P3_annexA_Delhi.json"},
                {"stem": "IS_875_Part_3_2015", "query": "Table 2 k2 terrain category 3", "quote": "| i) | 10 | 1.05 | 1.00 | 0.91 | 0.80 |", "found": True,
                 "cite": "IS 875 (Part 3):2015 Table 2: TC3 k2 0.91 (10 m), 0.97 (15 m), 1.01 (20 m)", "file": "rag/IS875_P3_table2_k2.json"},
                {"stem": "IS_875_Part_2_1987", "query": "Table 1 residential imposed load", "quote": "| i)(a)(1) | All rooms and kitchens | 2.0 | 1.8 |", "file": "rag/IS875_P2_table1_residential.json", "found": True,
                 "cite": "IS 875 (Part 2):1987 Table 1 dwellings 2.0 kN/m2; Table 2 roof 0.75; 3.1.2 partitions"},
                {"stem": "IS_875_Part_1_2026", "query": "unit weights cement board screed", "quote": "This code (Part 1) covers unit weight of materials", "file": "rag/IS875_P1_scope_unit_weights.json", "found": True,
                 "cite": "IS 875 (Part 1):2026 Table 1 unit weights (floor assembly 1.5 kN/m2)"},
                {"stem": "IS_875_Part_5_1987", "query": "8.1 load combinations working stress", "quote": "the following loading combinations, whichever combination produces the most unfavourable effect", "file": "rag/IS875_P5_8_1_combinations.json", "found": True,
                 "cite": "IS 875 (Part 5):1987 8.1 DL; DL+IL; DL+WL; DL+EL; DL+IL+WL; DL+IL+EL; Notes 4/5 0.9 DL"},
                {"stem": "IS_801_1975", "query": "6.1 basic design stress 6.1.2 wind earthquake", "quote": "6.1.2 Wind, Earthquake, and Combined Forces", "file": "rag/IS801_6_1_6_1_2.json", "found": True,
                 "cite": "IS 801:1975 6.1 F = 0.60 Fy; 6.1.2 33 1/3 percent for wind / earthquake; 8.1 wall studs"},
                {"stem": "IS_811_1987", "query": "Table 6 CLR100X50X15X2 CLR180X50X20X3.15", "quote": "TABLE 6 CHANNELS WITH LIPS-RECTANGULAR", "file": "rag/IS811_table6.json", "found": True,
                 "cite": "IS 811:1987 Table 6 channels with lips (corpus structured/sections.csv)"},
                {"stem": "IS_800_2007", "query": "Section 12.8 SCBF Table 4", "quote": "12.8 Special Concentrically Braced Frames (SCBF)", "file": "rag/IS800_12_8_SCBF.json", "found": True, "purpose": "lateral_frame_is800",
                 "cite": "IS 800:2007 Table 4; 12.8 special concentrically braced frames (hot-rolled lateral frame, D3)"},
                {"stem": "IS_18168_2023", "query": "1.3 zone IV residential SCBF", "quote": "In seismic zone V, all steel buildings shall be made of EBF systems; SCBFs shall not be used.", "file": "rag/IS18168_1_3.json", "found": True, "purpose": "lateral_frame_is800",
                 "cite": "IS 18168:2023 1.2 / 1.3: mandatory in Zone IV residential; SCBF permitted (EBF only in Zone V)"},
            ],
        },
    }
    return cfg


def main():
    import india_cfs_pipeline as CP
    cfg = build_cfg()
    (JOB / "cfg_snapshot.json").write_text(json.dumps(cfg, indent=1, default=str))
    out = CP.design_and_report(NAME, cfg, outdir=str(JOB))
    print(json.dumps({k: out[k] for k in out if k in ("status", "reasons", "report_html", "lateral_status")}, indent=1, default=str)[:4000])
    return out


if __name__ == "__main__":
    main()
