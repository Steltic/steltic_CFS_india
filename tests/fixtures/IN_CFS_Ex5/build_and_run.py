#!/usr/bin/env python3
"""IN_CFS_Ex5 -- two-span ALL-CFS portal warehouse + mezzanine, Hyderabad (Zone II): elastic seismic design (R = 1.0,
owner ruling), IS 801 working-stress members, IS 811 sections, wave-2 end-to-end run (CFS implementer).

Design decisions (the 'agent'):
  * Site: Hyderabad, IS 1893 Annex E Zone II Z = 0.10 (rag/IS1893_annexE_Hyderabad.json), medium soil (II);
    IS 875-3 Annex A Vb = 44 m/s (rag/IS875_P3_annexA_Hyderabad.json), terrain category 2 (open), Table 2 k2
    (rag/IS875_P3_table2_k2.json); inland: Kd 0.9, k4 1.0 (D10).  Snow: IS 875 Part 4 scope is the Himalayan /
    snow-bound region; Hyderabad has no design snow (found:false, rag/IS875_P4_snow_scope.json).
  * Occupancy: general-storage warehouse (no food storage stated) -> I = 1.0 (IS 1893 Table 8 (iii), D8).
  * Portal: 2 x 12 m spans, eave 7.0 m, apex 8.4 m (pitch 13.1 deg), frames at 5.0 m, 7 frames (30 m); columns and
    rafters 2 x CLR250X80X25X5 back to back (IS 801 7.3 connectors at 600 mm), FIXED bases (IS 800 Annex D sway K:
    pinned bases give K > 2.8 and KL/r > 200, 6.6.3); fly braces to the inner flange at every second girt / purlin
    (L_unbraced 3000 mm); IS 1079 grade 30 kgf/mm2 -> Fy 294 MPa (IS 801 Table 2 F = 1800 kgf/cm2).
  * Mezzanine: 12 m x 8 m over the first span at the end bay, at 3.5 m, on INDEPENDENT cold-formed posts (2 x CLR150X50X25X4
    at 3 m x 3 m); storage floor IL 7.5 kN/m2 (IS 875-2 Table 1 viii(a) minimum for warehouses, rag/IS875_P2_table1_storage.json),
    D 1.5; its seismic weight (D + 50 % IL, Table 10) enters the portal at 3.5 m (elastic, R 1.0).
  * Seismic basis: elastic_R1 (statement in the report); IS 800 Section 12 not applicable; wind governs.
  * Longitudinal: X-bracing (CLR150X50X20X3.15) in 3 side-wall bays each side; roof plan bracing declared by the EOR.
  * Loads: D_roof 0.35 kN/m2 (0.45 mm GI sheeting 0.05 + purlins 0.10 + insulation / services 0.20, IS 875-1);
    Lr = 0.75 - 0.02 x 3.1 = 0.69 kN/m2 (IS 875-2 Table 2 (ii), rag/IS875_P2_table2_roof.json); cladding 0.20 kN/m2.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

JOB = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "steel_engine"))
os.environ.setdefault("STEEL_BUILDER_JOBS", str(REPO / "tests" / "_jobs"))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import india_cfs_env  # noqa: E402,F401

NAME = "IN_CFS_Ex5_Portal_allCFS_elastic_Hyderabad"


def build_cfg():
    cfg = {
        "name": NAME, "jurisdiction": "india", "units": "m", "design_basis": "IS801_WSM", "all_cfs_portal": True,
        "brief": "IN_CFS_Ex5 two-span CFS portal warehouse + mezzanine, Hyderabad; owner ruling: ALL-CFS portal designed elastically (R 1.0)",
        "site": {"city": "Hyderabad", "zone": "II", "Z": 0.10, "soil": "II", "Vb": 44.0, "Vb_source": "IS 875-3 Annex A (Hyderabad 44 m/s)",
                 "terrain_category": 2, "k1": 1.0, "k3": 1.0, "cyclone_belt": False,
                 "cyclone_belt_cite": "Hyderabad is inland (Deccan), outside the 60 km east-coast / Gujarat belt (IS 875-3 6.3.4); Kd 0.9 (7.2.1)",
                 "Kd": 0.9, "k2_table": {10: 1.00, 15: 1.05, 20: 1.07, 30: 1.12}, "wind_structure_class": "industrial"},
        "occupancy": {"use": "warehouse (general storage)", "area_m2": 24 * 30, "food_storage": False,
                      "note": "general storage, no food storage stated -> IS 1893 Table 8 (iii) I = 1.0 (D8)"},
        "geometry": {"plan_x_m": 24.0, "plan_y_m": 30.0, "heights_m": [7.0]},
        "portal": {"spans_m": [12.0, 12.0], "eave_m": 7.0, "apex_m": 8.4, "spacing_m": 5.0, "n_frames": 7, "length_m": 30.0,
                   "girt_spacing_m": 1.5, "purlin_spacing_m": 1.5, "base": "fixed", "opening_ratio": 0.05, "seismic_basis": "elastic_R1",
                   "knee_brace": {"col_below_eave_m": 2.5, "raf_from_knee_m": 3.0}},
        "loads": {"D_roof": 0.35, "Lr": 0.69, "clad": 0.20, "snow": 0.0, "D_floor": 0.0, "L_floor": 0.0,
                  "snow_note": "IS 875 (Part 4):2021 snow: Himalayan / snow-bound scope; Hyderabad no design snow (found:false)",
                  "cite": "IS 875-1 Table 1 sheeting / purlins; IS 875-2 Table 2 (ii) sloping roof > 10 deg: 0.75 - 0.02/deg = 0.69 kN/m2"},
        "mezzanine": {"height_m": 3.5, "depth_m": 8.0, "span_index": 0, "D_kNm2": 1.5, "L_kNm2": 7.5, "support": "independent_posts", "lateral": "own_bracing",
                      "lateral_note": "the mezzanine is braced to the ground by its own X-bracing (tension diagonals per IS 801 6.1 / 7.5) and does not push the portal",
                      "bracing": {"section": "CLR100X50X15X2", "n_ply": 1, "bay_m": 3.0, "n_braced_bays_x": 2, "n_braced_bays_y": 2,
                                  "n_bolts_at_section": 2, "d_bolt_mm": 12.0, "tension_only": True,
                                  "note": "X-braced post bays (2 per direction) between the mezzanine deck and the slab"},
                      "use": "storage mezzanine (bulk storage <= 3 m high)",
                      "L_cite": "IS 875 (Part 2):1987 Table 1 viii(a) warehouses: 2.4 kN/m2 per m of storage height, minimum 7.5 kN/m2",
                      "posts": {"section": "CLR150X50X25X4", "n_ply": 2, "trib_m2": 9.0, "note": "posts at 3 m x 3 m, pinned ends"}},
        "cfs_members": {
            "Fy_MPa": 294.0, "grade_cite": "IS 1079 sheet, IS 801 Table 2 yield 30 kgf/mm2 (294 MPa) -> F = 1800 kgf/cm2",
            "columns": {"section": "CLR250X80X25X5", "n_ply": 2, "L_unbraced_mm": 3000.0, "connector_spacing_mm": 600.0},
            "rafters": {"section": "CLR250X80X25X5", "n_ply": 2, "L_unbraced_mm": 3000.0, "connector_spacing_mm": 600.0},
            "knee_braces": {"section": "CLR150X50X25X4", "n_ply": 2},
            "purlins": {"section": "CLR150X50X20X3.15", "spacing_mm": 1500.0, "span_mm": 5000.0, "roof_pitch_deg": 13.1,
                        "L_unbraced_mm": 3000.0, "L_unbraced_top_mm": 0.0, "bearing_mm": 60.0,
                        "wind_uplift_kNm2": None, "wind_pressure_kNm2": None,
                        "deflection_limit_ratio": 150, "deflection_cite": "IS 800:2007 Table 6 (read-only): purlins, elastic cladding, span/150"},
            "girts": {"section": "CLR150X50X20X3.15", "spacing_mm": 1500.0, "span_mm": 5000.0, "L_unbraced_mm": 3000.0,
                      "wind_suction_kNm2": None, "wind_pressure_kNm2": None,
                      "deflection_limit_ratio": 150, "deflection_cite": "IS 800:2007 Table 6 (read-only): girts, elastic cladding, span/150"},
            "joists": {"section": "CLR200X80X25X4", "n_ply": 1, "spacing_mm": 500.0, "span_mm": 3000.0, "bearing_mm": 60.0,
                       "compression_flange_restrained": True, "deflection_limit_ratio": 300,
                       "deflection_cite": "IS 800:2007 Table 6 (read-only): floor, elements not susceptible to cracking, span/300",
                       "note": "mezzanine joists between the post beams (3 m)"},
        },
        "cfs_connections_spec": {
            "knee": {"rows": 6, "cols": 2, "pitch_mm": 60.0, "gauge_mm": 120.0, "d_mm": 16.0, "edge_mm": 30.0, "bolt_class": "4.6"},
            "apex": {"rows": 4, "cols": 2, "pitch_mm": 60.0, "gauge_mm": 120.0, "d_mm": 16.0, "edge_mm": 30.0, "bolt_class": "4.6"},
            "base": {"B_mm": 500.0, "L_mm": 600.0, "t_plate_mm": 40.0, "fy_plate_MPa": 240.0, "fu_plate_MPa": 410.0, "col_d_mm": 250.0,
                     "anchors": {"n_total": 6, "n_tension": 3, "d_mm": 24.0, "grade": "4.6", "f_mm": 250.0, "pitch_mm": 150.0, "edge_mm": 50.0},
                     "bearing_permissible_MPa": 6.0,
                     "bearing_cite": "EOR input -- permissible bearing on the M25 pedestal 6.0 MPa (working stress); IS 456 is not in the corpus -- VERIFY"},
        },
        "longitudinal_bracing": {"section": "CLR150X50X20X3.15", "n_ply": 1, "n_braced_bays": 3, "n_bolts_at_section": 2, "d_bolt_mm": 16.0, "tension_only": True,
                                 "note": "X-bracing in three side-wall bays each side + roof plan bracing between the same frames (EOR detail)"},
        "load_plan": {
            "jurisdiction": "india", "design_basis": "IS801_WSM", "lateral_frame_basis": None, "cfs_combinations": "auto", "combinations": None,
            "retrieval": [
                {"stem": "IS_1893_Part_1_2016", "query": "Annex E Hyderabad zone", "found": True, "cite": "IS 1893 (Part 1):2016 Annex E: Hyderabad Zone II, Z 0.10", "file": "rag/IS1893_annexE_Hyderabad.json"},
                {"stem": "IS_1893_Part_1_2016", "query": "Table 8 importance factor warehouse", "found": True, "cite": "IS 1893 Table 8 (iii): general storage I 1.0 (D8; 1.5 only for food storage)"},
                {"stem": "IS_1893_Part_1_2016", "query": "6.4.2 Ah 7.6 ESM single storey Zone II", "found": True, "cite": "IS 1893 6.4.2 Ah = (Z/2)(I/R)(Sa/g); 7.6 ESM for regular < 15 m in Zone II; 7.11.1.1 drift 0.004 h"},
                {"stem": "IS_875_Part_3_2015", "query": "Annex A Hyderabad basic wind speed", "found": True, "cite": "IS 875 (Part 3):2015 Annex A Hyderabad 44 m/s", "file": "rag/IS875_P3_annexA_Hyderabad.json"},
                {"stem": "IS_875_Part_3_2015", "query": "Table 2 k2 terrain category 2", "found": True, "cite": "IS 875 (Part 3):2015 Table 2: TC2 k2 1.00 (10 m), 1.05 (15 m), 1.07 (20 m)", "file": "rag/IS875_P3_table2_k2.json"},
                {"stem": "IS_875_Part_3_2015", "query": "Table 5 Table 6 Cpe walls pitched roof Cpi 7.3.2", "found": True, "cite": "IS 875 (Part 3):2015 Tables 5 / 6, 7.3.2.1 Cpi +-0.2 (openings <= 5 %)"},
                {"stem": "IS_875_Part_2_1987", "query": "Table 1 storage buildings warehouses", "found": True, "cite": "IS 875 (Part 2):1987 Table 1 viii(a): 2.4 kN/m2 per m storage height, min 7.5 kN/m2", "file": "rag/IS875_P2_table1_storage.json"},
                {"stem": "IS_875_Part_2_1987", "query": "Table 2 sloping roof imposed load", "found": True, "cite": "IS 875 (Part 2):1987 Table 2 (ii): 0.75 - 0.02 kN/m2 per degree over 10 deg", "file": "rag/IS875_P2_table2_roof.json"},
                {"stem": "IS_875_Part_1_2026", "query": "unit weights sheeting", "found": True, "cite": "IS 875 (Part 1):2026 Table 1 unit weights (roof assembly 0.35 kN/m2)"},
                {"stem": "IS_875_Part_4_1987", "query": "snow load Hyderabad", "found": False, "cite": None, "file": "rag/IS875_P4_snow_scope.json",
                 "note": "IS 875 (Part 4):2021 snow-bound scope; no design snow for Hyderabad (found:false)"},
                {"stem": "IS_875_Part_5_1987", "query": "8.1 load combinations working stress", "found": True, "cite": "IS 875 (Part 5):1987 8.1 DL; DL+IL; DL+WL; DL+EL; DL+IL+WL; DL+IL+EL; Notes 4/5 0.9 DL"},
                {"stem": "IS_801_1975", "query": "6.1 6.1.2 6.3 6.6 6.7 7.3 7.5", "found": True, "cite": "IS 801:1975 6.1 F = 0.60 Fy; 6.1.2; 6.3; 6.6.1.1; 6.7.1; 7.3; 7.5"},
                {"stem": "IS_811_1987", "query": "Table 6 CLR250X80X25X5 CLR150X50X20X3.15", "found": True, "cite": "IS 811:1987 Table 6 channels with lips (corpus structured/sections.csv)"},
                {"stem": "IS_800_2007", "query": "Table 6 deflection limits; Annex D effective length sway; 11.6.2 bolts working stress", "found": True,
                 "purpose": "serviceability_limits_table6", "cite": "IS 800:2007 Table 6 Height/150; Annex D sway K; 11.6.2 / 11.4.1(c) working stress",
                 "file": "rag/IS800_table6_deflection.json"},
            ],
        },
    }
    return cfg


def main():
    import india_cfs_pipeline as CP
    cfg = build_cfg()
    out = CP.design_and_report(NAME, cfg, outdir=str(JOB))
    print(json.dumps({k: out[k] for k in out if k in ("status", "n_reasons", "reasons", "report_html")}, indent=1, default=str)[:6000])
    return out


if __name__ == "__main__":
    main()
