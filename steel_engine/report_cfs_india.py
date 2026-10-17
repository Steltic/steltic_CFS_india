"""report_cfs_india.py -- the HTML report of an India CFS job (spec WP3.6): IS units only (kN, kN/m, kN/m2, kN-m, m,
mm, MPa), the two labelled combination families, the lateral system (hot-rolled frame summary with a link to its own
report, or the all-CFS portal), every IS 801 member check with its compression-flange restraint, the diaphragm path,
connections, durability / fire / acoustics, the IS grounding table and the design status.  No US clause string is
written here (india_cfs_gates.US_RE is asserted by consistency.check on the rendered file).

2026-10 first wave (review items 5-8): building-type titles (CFS-led for portal / purlin jobs, "hot-rolled frame with
LGSF infill and floors" for the multi-storey jobs), no raw Python dicts, no float noise, moments in kN-m and forces in
kN, plain-English importance-factor basis, grade and coating stated, per-row combination citations, girts in
'suction', and no internal labels (rulings, engine hashes, fallbacks) in client-facing text.
"""
from __future__ import annotations
import html
import os
import re

import india_cfs_env  # noqa: F401
import india_cfs_basis as B

UNITS = {"force": "kN", "moment": "kN-m", "length": "m", "small_length": "mm", "pressure": "kN/m2", "line_load": "kN/m",
         "stress": "MPa", "engine": "N, mm, MPa (IS 801 kgf/cm2 inside is801_members)"}
COASTAL_CITIES = ("chennai", "visakhapatnam", "vizag", "surat", "mumbai", "kolkata", "kochi", "mangaluru", "mangalore",
                  "puducherry", "thiruvananthapuram", "goa", "panaji", "bhubaneswar", "puri", "kakinada", "tuticorin",
                  "thoothukudi", "porbandar", "veraval", "kandla", "dwarka")
ACOUSTIC_USES = ("residen", "apartment", "hostel", "dormitor", "hotel", "motel", "clinic", "hospital", "senior", "student")


def _set_report_units(cfg):
    """WP3.6: the report always displays kN / kN-m / m / mm / kN/m2 / MPa; engine values are N, mm."""
    u = dict(UNITS)
    if str((cfg or {}).get("units") or "m").lower() not in ("m", "mm", "metric", "si", "n-mm"):
        raise ValueError("India report: cfg['units'] must be metric (got %r)" % cfg.get("units"))
    return u


def _num(v, nd=3):
    """A number for display without float noise (13.799999999999999 -> 13.8, 0.7999999 -> 0.8)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return "-" if v is None else str(v)
    s = ("%%.%df" % nd) % float(v)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _kN(v, d=1):
    return "-" if not isinstance(v, (int, float)) else ("%%.%df" % d) % (v / 1e3)


def _kNm(v, d=2):
    return "-" if not isinstance(v, (int, float)) else ("%%.%df" % d) % (v / 1e6)


def _f(v, d=3):
    return "-" if not isinstance(v, (int, float)) else ("%%.%df" % d) % v


def _dcf(v, d=3):
    """RR-BUG-3: a D/C for display -- 'not evaluated' when there is none."""
    return _f(v, d) if isinstance(v, (int, float)) else "not evaluated"


def _e(s):
    return html.escape(str(s if s is not None else "-"))


def _t(headers, rows):
    h = "".join("<th>%s</th>" % _e(x) for x in headers)
    b = "".join("<tr>" + "".join("<td>%s</td>" % _e(c) for c in r) + "</tr>" for r in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (h, b)


def _ok(v):
    return {True: "PASS", False: "FAIL", None: "not evaluated"}.get(v, str(v))


# internal labels never printed in a client-facing report (review item 7)
_CLEAN = [
    (re.compile(r"\(?\s*owner ruling D8[^;:)]*\)?\s*[:;]?\s*", re.I), ""),
    (re.compile(r"\(?\s*owner ruling [A-Z]\d+(?:\s*[:,]\s*[^;)]*)?\)?", re.I), ""),
    (re.compile(r"\(?\s*\bruling R\d+\b(?:\s*[:,]\s*[^;)]*)?\)?", re.I), ""),
    (re.compile(r"\bowner ruling\b:?\s*", re.I), ""),
    (re.compile(r"\((?:D\d+|L\d+|WP\d+(?:\.\d+)?)(?:\s*/\s*(?:D\d+|L\d+|WP\d+(?:\.\d+)?))*\)"), ""),
    (re.compile(r"\bD3 rewrite\b", re.I), ""),
    (re.compile(r"(?<![\w.])(?:D|L|R)\d{1,2}(?:\s*/\s*(?:D|L|R)\d{1,2})*\s*:\s*"), ""),
    (re.compile(r";\s*:"), ";"),
    (re.compile(r"\bdecision D\d+\b", re.I), ""),
    (re.compile(r"\s*\(in-repo fallback; prefer corpus exact_table 5\)", re.I), ""),
    (re.compile(r"in-repo fallback; prefer corpus exact_table 5", re.I), ""),
    (re.compile(r"\bvendored HR India pipeline\b", re.I), "hot-rolled IS 800 engine"),
    (re.compile(r"\bGOLD(?: round \d+)?\b:?\s*", re.I), ""),
    (re.compile(r"\bEOR\b"), "design engineer"),
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"\(\s*\)"), ""),
    (re.compile(r"\s+([;,.)])"), r"\1"),
]


def clean(text):
    """Free text from the cfg / engine as printed: internal labels removed, 'EOR' spelt out."""
    s = str(text if text is not None else "")
    for rx, rep in _CLEAN:
        s = rx.sub(rep, s)
    return s.strip(" ;,")


# ---------------------------------------------------------------------------------------------------------------
# titles (review item 6)
# ---------------------------------------------------------------------------------------------------------------
def building_kind(cfg, pkg=None):
    """'portal_cfs' (all-cold-formed portal), 'portal_hr' (hot-rolled portal with CFS purlins / girts) or 'hybrid'
    (hot-rolled braced / moment frame with LGSF infill walls and cold-formed floor joists)."""
    if (cfg or {}).get("all_cfs_portal"):
        return "portal_cfs"
    cm = (cfg or {}).get("cfs_members") or {}
    if (cfg or {}).get("portal") and not cm.get("studs") and not cm.get("joists"):
        return "portal_hr"
    if (cfg or {}).get("portal") and (cm.get("purlins") or cm.get("girts")) and not cm.get("joists"):
        return "portal_hr"
    return "hybrid"


def _frame_words(cfg):
    lf = (cfg or {}).get("lateral_frame") or {}
    sysn = str((lf.get("hr_cfg_extra") or {}).get("system") or lf.get("system") or "").upper()
    braced = any(k in sysn for k in ("CBF", "OBF", "SBF", "EBF"))
    moment = any(k in sysn for k in ("SMF", "SMRF", "OMF", "OMRF"))
    if braced and moment:
        return "braced and moment frame"
    if moment:
        return "moment frame"
    return "braced frame"


def report_title(cfg, pkg=None):
    """Report title by building type; cfg['report_title'] overrides."""
    if (cfg or {}).get("report_title"):
        return str(cfg["report_title"])
    k = building_kind(cfg, pkg)
    if k == "portal_cfs":
        return "All-cold-formed portal frame building (IS 801)"
    if k == "portal_hr":
        return "Cold-formed purlins and girts on a hot-rolled %s (IS 801 / IS 800)" % (
            "portal frame" if "moment" in _frame_words(cfg) else _frame_words(cfg))
    return "Hot-rolled %s with LGSF infill walls and cold-formed floor joists (IS 800 / IS 801)" % _frame_words(cfg)


CSS = """<style>body{font-family:Georgia,serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#222}
table{border-collapse:collapse;margin:8px 0 16px;font-size:13px}th,td{border:1px solid #bbb;padding:3px 6px;text-align:left}
th{background:#eee}h1{font-size:22px}h2{font-size:18px;margin-top:28px;border-bottom:1px solid #999}.st{padding:8px;border:2px solid #333}
.fail{color:#a00;font-weight:bold}.note{font-size:12px;color:#555}.rs{font-size:12px;color:#234}</style>"""


# ---------------------------------------------------------------------------------------------------------------
# formatting helpers for engine records
# ---------------------------------------------------------------------------------------------------------------
def _val_units(v, units):
    """(display value, unit label) for a check row value / limit in engine units."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return ("-" if v is None else str(v)), ""
    if units == "N-mm":
        return "%.2f" % (v / 1e6), "kN-m"
    if units == "N":
        return "%.2f" % (v / 1e3), "kN"
    if units == "MPa":
        return "%.1f" % v, "MPa"
    if units == "mm":
        return "%.1f" % v, "mm"
    if units == "N/mm":
        return "%.2f" % v, "N/mm"
    return "%.3f" % v, ""


def short_restraint(text):
    """Compact per-row form of a restraint statement (the full statement is printed once per member)."""
    t = str(text or "")
    if not t:
        return "-"
    m = re.search(r"compression flange: (\w+)[^,]*?, continuously restrained by (.+?)(?:$|;| \()", t)
    if m:
        return "%s flange restrained by %s" % (m.group(1), m.group(2).replace("the ", ""))
    m = re.search(r"compression flange: (\w+).*?braced at (?:a = )?(\d+) mm(?: by (\d+) ([\w -]+?line\(s\)|[\w -]+?brace\(s\)))?", t)
    if m:
        return "%s flange braced at %s mm%s" % (m.group(1), m.group(2), (" (%s %s)" % (m.group(3), m.group(4))) if m.group(3) else "")
    m = re.search(r"compression flange: (\w+).*?UNBRACED over (\d+) mm", t)
    if m:
        return "%s flange UNBRACED over %s mm" % (m.group(1), m.group(2))
    m = re.search(r"compression flange: (\w+) \(free\) in the hogging zone.*?, (\d+) mm", t)
    if m:
        return "%s flange, hogging zone, %s mm to contraflexure" % (m.group(1), m.group(2))
    m = re.search(r"sheathing on both faces at a = (\d+) mm", t)
    if m:
        return "both flanges braced by sheathing at %s mm (8.1)" % m.group(1)
    m = re.search(r"UNBRACED over its height (\d+) mm", t)
    if m:
        return "UNBRACED over the height %s mm" % m.group(1)
    return t[:90]


def _occupancy_text(occ):
    occs = occ if isinstance(occ, list) else ([occ] if isinstance(occ, dict) else [])
    out = []
    for o in occs:
        bits = [clean(o.get("use") or "-")]
        if o.get("area_m2") is not None:
            bits.append("floor area %s m2" % _num(o["area_m2"], 0))
        if o.get("persons") is not None:
            bits.append("%s persons" % _num(o["persons"], 0))
        if o.get("note") and not re.search(r"proxy|ruling", str(o["note"]), re.I):
            n = clean(o["note"])           # notes about an area proxy / ruling are replaced by the importance-factor row
            if n:
                bits.append(n)
        out.append(", ".join(bits))
    return "; ".join(out) if out else "-"


def importance_text(ss, occ):
    """Plain statement of the occupancy basis for I (review items 7 / 11): never 'area proxy' / 'owner ruling'."""
    I = ss.get("I")
    row = str(ss.get("I_row") or "")
    occs = occ if isinstance(occ, list) else ([occ] if isinstance(occ, dict) else [])
    use = "; ".join(clean(o.get("use") or "") for o in occs if isinstance(o, dict)) or "-"
    area = sum(float(o.get("area_m2") or 0.0) for o in occs if isinstance(o, dict))
    persons = [o.get("persons") for o in occs if isinstance(o, dict) and o.get("persons") is not None]
    if "clinic" in row.lower():
        return ("I = %s: outpatient clinic (%s) -- not a hospital building with in-patient beds, so the IS 1893 (Part 1):2016 "
                "Table 8 (i) row (I = 1.5) is not applied; the design engineer adopts 1.2. Confirm with the client whether "
                "the clinic is an essential facility, in which case Table 8 (i) governs." % (_f(I, 1), use))
    if "area" in row.lower() or "d8" in row.lower():
        return ("I = %s: IS 1893 (Part 1):2016 Table 8 (ii) row (residential / commercial buildings with occupancy of more than "
                "200 persons). Occupancy basis: %s, %s m2 of floor area; the brief gives no occupant count and the "
                "floor area is taken as housing more than 200 persons -- the design engineer confirms the count."
                % (_f(I, 1), use, _num(area, 0)))
    if persons:
        return "I = %s: IS 1893 (Part 1):2016 %s -- %s, %s persons" % (_f(I, 1), clean(row) or "Table 8", use,
                                                                       " + ".join(_num(p, 0) for p in persons))
    return "I = %s: IS 1893 (Part 1):2016 %s -- %s" % (_f(I, 1), clean(row) or "Table 8", use)


def _cpe_text(c):
    if isinstance(c, dict):
        bits = []
        for k in ("windward", "leeward"):
            if c.get(k) is not None:
                bits.append("%s %+.2f" % (k, float(c[k])))
        if c.get("net") is not None:
            bits.append("net %.2f" % float(c["net"]))
        return ", ".join(bits) or "-"
    return "-" if c in (None, "") else clean(c)


def _wind_member_text(m):
    w = m.get("wind") or {}
    mp = w.get("member_pd") or {}
    if not mp:
        return None
    sel = [mp.get("general") or {}, mp.get("edge") or {}]
    out = ("member wind (IS 875-3 7.3): element area %s m2 at z = %s m, pz %s kN/m2, Ka %s, Cpe %s / %s, Cpi +-%s (%s) -> "
           "pressure %s kN/m2, %s %s kN/m2"
           % (_num(mp.get("A_m2"), 2), _num(mp.get("z_m"), 2), _num(mp.get("pz_kNm2"), 3), _num(mp.get("Ka"), 3),
              _num(mp.get("Cpe_max"), 2), _num(min([x.get("Cpe_min", 0) for x in sel if x.get("Cpe_min") is not None]
                                                    + [x.get("Cpe_local", 0) for x in sel if x.get("Cpe_local") is not None]
                                                    or [mp.get("Cpe_min") or 0.0]), 2),
              _num(mp.get("Cpi"), 2), clean(mp.get("Cpi_basis")), _num(mp.get("p_in_kNm2"), 3),
              "suction" if m.get("role") in ("girt", "stud") else "uplift / suction", _num(mp.get("p_out_kNm2"), 3)))
    if w.get("p_design_kNm2") is not None:
        out += "; design pressure %s kN/m2" % _num(w["p_design_kNm2"], 3)
    return out


def _axial_text(a):
    if not a:
        return None
    return ("axial: dead %s kN, imposed %s kN per stud (%s)" % (_kN(a.get("P_dead_N"), 2), _kN(a.get("P_live_N"), 2),
                                                               clean(a.get("note"))))


def _member_header(m):
    sp = "spacing %s mm, " % _num(m.get("spacing_mm"), 0) if m.get("spacing_mm") is not None else ""
    ln = m.get("length_mm") or m.get("span_mm") or m.get("height_mm")
    role = str(m.get("role") or "")
    word = "height" if role in ("stud", "column", "mezzanine post") else (
        "span" if role in ("joist", "purlin", "girt", "header", "eave_strut", "mezzanine beam") else "length")
    lt = ("%s %s mm, " % (word, _num(ln, 0))) if ln else ""
    return ("%s -- %s (%s), Fy %s MPa, %s%sD/C %s (%s)"
            % (m["id"], m.get("designator"), m.get("role"), _num(m.get("Fy_MPa"), 0), sp, lt, _dcf(m.get("DC")), _ok(m.get("ok"))))


def durability_text(cfg, pkg):
    """One 'Durability, fire and acoustics' paragraph per report (review item 8; design engineer's items)."""
    site = (cfg or {}).get("site") or {}
    city = str(site.get("city") or "")
    mats = sorted({str(m.get("material")) for m in (pkg.get("cfs_members") or []) if m.get("material")})
    coastal = site.get("coastal_exposure")
    if coastal is None:
        coastal = any(c in city.lower() for c in COASTAL_CITIES)
    occ = (cfg or {}).get("occupancy")
    occs = occ if isinstance(occ, list) else ([occ] if isinstance(occ, dict) else [])
    uses = " ".join(str(o.get("use") or "") for o in occs if isinstance(o, dict)).lower()
    parts = []
    parts.append("<b>Durability, fire and acoustics</b> (the design engineer's items; not checked in this report). "
                 "Steel and coating: %s." % _e("; ".join(clean(x) for x in mats) or "as declared"))
    if coastal:
        parts.append("Corrosion: %s is a coastal / marine-influenced site. Z275 is a minimum for dry, enclosed members only; "
                     "members exposed to the coastal atmosphere (eaves, open bays, girts behind ventilated cladding, "
                     "members near openings) need a heavier coating class than Z275 -- for example a heavier zinc class "
                     "or an aluminium-zinc AZ150 / AZ200 coating (IS 15961) -- or an added paint system to IS 4180, "
                     "with dissimilar metals isolated; the design engineer fixes the class for each exposure zone."
                     % _e(city))
    else:
        parts.append("Corrosion: %s is an inland site; Z275 suits dry, enclosed members -- humid or open zones need a heavier "
                     "coating class or a paint system to IS 4180." % _e(city or "the site"))
    parts.append("Fire: the fire-resistance period that NBC 2016 Part 4 requires for this occupancy and height is "
                 "provided by tested board-lining, ceiling or encasement assemblies; the cold-formed members are not "
                 "designed for fire here.")
    if any(u in uses for u in ACOUSTIC_USES):
        parts.append("Acoustics: separating walls and floors between dwellings / rooms need the sound-insulation rating of "
                     "a tested lining system (stud or joist depth, cavity insulation, resilient fixing).")
    else:
        parts.append("Acoustics: no separating-wall or floor sound-insulation requirement for this use.")
    tC = (cfg or {}).get("service_temperature_C")
    if tC is not None and float(tC) < 0:
        parts.append("Cold service: the %s deg C cold room needs a toughness statement. IS 2062:2025 quality C is impact "
                     "tested at -20 deg C, which is warmer than the service temperature: for hot-rolled members inside the "
                     "cold envelope order impact testing at or below %s deg C (IS 2062 12.5, by agreement) or keep them on "
                     "the warm side of the insulation; thin cold-formed sheet cannot be Charpy tested (IS 2062 12.1.1, "
                     "6 mm minimum), so keep the cold-formed members and their fasteners outside the cold envelope or "
                     "use a supplier-certified low-temperature grade and fastener class." % (_num(tC, 0), _num(tC, 0)))
    return "<p>%s</p>" % " ".join(parts)


# ---------------------------------------------------------------------------------------------------------------
def build_report_cfs_india(name, cfg, pkg, root):
    u = _set_report_units(cfg)
    site = cfg.get("site") or {}; lat = pkg.get("lateral_frame") or {}; lp = cfg.get("load_plan") or {}
    ss = lat.get("seismic_summary") or {}
    st = pkg.get("design_status") or {}
    kind = building_kind(cfg, pkg)
    portal = kind == "portal_cfs"
    title = report_title(cfg, pkg)
    out = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title>%s</head><body>" % (_e(name), CSS)]
    out.append("<h1>%s</h1>" % _e(title))
    out.append("<p class='note'>Job %s -- India cold-formed steel design report (IS 801:1975 (Reaffirmed 2021) / "
               "IS 811:1987)</p>" % _e(name))
    out.append("<p class='note'>%s</p>" % _e(B.basis_statement(cfg)))
    out.append("<div class='st'>Design status: <b>%s</b> -- %d open item(s)%s</div>"
               % (_e(str(st.get("status", "")).upper()), st.get("n_reasons", 0),
                  "" if not st.get("n_reasons") else " (listed in the last chapter; items inherited from the hot-rolled frame "
                                                     "report are included)"))
    # ---- 1 building ----
    out.append("<h2>1. Building, site and load path</h2>")
    geo = cfg.get("geometry") or {}
    lf = cfg.get("lateral_frame") or {}
    hs = geo.get("heights_m") or []
    if portal:
        po = cfg.get("portal") or {}
        lat_row = ("cold-formed portal frames (%s), %s frames at %s m, eave %s m, apex %s m; earthquake designed elastically "
                   "(R = 1.0, no ductility claimed); longitudinal X-bracing in cold-formed members"
                   % (" + ".join("%s m" % _num(x) for x in po.get("spans_m") or []), _num(po.get("n_frames"), 0),
                      _num(po.get("spacing_m")), _num(po.get("eave_m")), _num(po.get("apex_m"))))
        cfs_row = ("IS 801:1975 (Reaffirmed 2021) working stress for every member, the portal columns, rafters and knee "
                   "braces included (the lateral system); IS 811:1987 / computed thin sections")
    else:
        sysx = (lf.get("hr_cfg_extra") or {}).get("system")
        lat_row = "%s hot-rolled IS 800:2007 %s, R = %s (%s)" % (
            sysx or lat.get("system"), _frame_words(cfg), _num(lat.get("R")), clean(lat.get("R_cite")))
        if sysx and str(sysx) != str(lat.get("system")):
            lat_row += ("; R is the smaller of the components (IS 1893 Table 9), conservative for the %s direction"
                        % ("moment-frame" if "SMF" in str(sysx).upper() else "stiffer"))
        cfs_row = ("IS 801:1975 (Reaffirmed 2021) working stress; IS 811:1987 and computed thin sections; gravity and wind "
                   "members only (no seismic force-resisting role)")
    mats = sorted({str(m.get("material")) for m in (pkg.get("cfs_members") or []) if m.get("material")})
    out.append(_t(["item", "value"], [
        ("brief", clean(cfg.get("brief"))),
        ("site", "%s, IS 1893 Annex E Zone %s (Z = %s), soil type %s" % (site.get("city"), site.get("zone"), _num(site.get("Z")), site.get("soil"))),
        ("plan / storey heights", "%s m x %s m; storey heights %s m" % (_num(geo.get("plan_x_m")), _num(geo.get("plan_y_m")),
                                                                      ", ".join(_num(h) for h in hs) or "-")),
        ("lateral system", lat_row),
        ("cold-formed members", cfs_row),
        ("steel grade and coating", "; ".join(clean(x) for x in mats) or "-"),
        ("importance factor", importance_text(ss, cfg.get("occupancy"))),
        ("occupancy", _occupancy_text(cfg.get("occupancy"))),
        ("units", "kN, kN-m, m, mm, kN/m2, MPa (engine: N, mm, MPa)"),
    ]))
    # ---- 2 loads ----
    out.append("<h2>2. Loads (IS 875 Parts 1-5, IS 1893)</h2>")
    ld = cfg.get("loads") or {}
    names = [("D_floor", "floor dead load"), ("D_roof", "roof dead load"), ("L_floor", "floor imposed load"),
             ("Lr", "roof imposed load"), ("clad", "wall cladding"), ("partition_design_kNm2", "partition allowance (design)"),
             ("partition_seismic_kNm2", "partitions in the seismic weight"), ("snow", "snow"),
             ("collateral_kNm2", "collateral (services; non-permanent dead)"), ("pv_kNm2", "rooftop PV (non-permanent dead)")]
    rows = [(lab, _num(ld.get(k))) for k, lab in names if ld.get(k) is not None]
    rows.append(("basis", clean(ld.get("cite"))))
    out.append(_t(["gravity load", "kN/m2"], rows))
    ws = lp.get("wind_summary") or {}
    out.append("<p>Wind: IS 875 (Part 3):2015, Vb = %s m/s (%s), terrain category %s, k1 %s, k3 %s, k4 %s, Kd %s, Ka %s (frame "
               "tributary area), %s.</p>"
               % (_num(ws.get("Vb_mps")), _e(clean(ws.get("Vb_source")) or "IS 875-3 Annex A"), ws.get("terrain_category"),
                  _num(ws.get("k1")), _num(ws.get("k3")), _num(ws.get("k4")), _num(ws.get("Kd")), _num(ws.get("Ka")),
                  _e(("inside the cyclone belt: " if ws.get("cyclone_belt") else "outside the cyclone belt: ")
                     + clean(ws.get("cyclone_belt_cite")))))
    if ws.get("storeys"):
        out.append(_t(["storey", "z (m)", "k2", "Vz (m/s)", "pz (kN/m2)", "pd (kN/m2)"],
                      [(r["k"], _num(r["z_m"], 2), _num(r["k2"], 4), _num(r["Vz_mps"], 2), _num(r["pz_kNm2"], 4), _num(r["pd_kNm2"], 4))
                       for r in ws["storeys"]]))
    if portal:
        pats = ws.get("patterns") or []
        if pats:
            out.append(_t(["frame wind pattern (IS 875-3 Table 5 / 6)", "Cpi", "windward wall", "leeward wall",
                           "windward roof", "leeward roof"],
                          [(p.get("name"), _num(p.get("Cpi"), 2), _num(p.get("wall_windward_kNm2"), 3), _num(p.get("wall_leeward_kNm2"), 3),
                            _num(p.get("roof_windward_kNm2"), 3), _num(p.get("roof_leeward_kNm2"), 3)) for p in pats]))
            out.append("<p class='note'>Net pressures in kN/m2 (positive towards the surface) at pd = %s kN/m2, roof pitch %s deg. "
                       "Frame wind base shear (one frame, governing pattern %s): %s kN; earthquake base shear (one frame): %s kN "
                       "-- %s governs.</p>"
                       % (_num(ws.get("pd_kNm2"), 4), _num(ws.get("pitch_deg"), 1), _e((lat.get("wind_vs_eq") or {}).get("governing_wind_pattern")),
                          _num((lat.get("wind_vs_eq") or {}).get("H_base_wind_kN"), 2), _num((lat.get("wind_vs_eq") or {}).get("H_base_eq_kN"), 2),
                          _e((lat.get("wind_vs_eq") or {}).get("governing"))))
    elif ws.get("storeys") or ws.get("Cpe_X"):
        out.append("<p>Wall Cpe (IS 875 (Part 3):2015 Table 5, 7.3.3.1): X %s; Y %s. Wind base shear X %s kN, Y %s kN.</p>"
                   % (_e(_cpe_text(ws.get("Cpe_X"))), _e(_cpe_text(ws.get("Cpe_Y"))), _f(ws.get("VB_x_kN"), 1), _f(ws.get("VB_y_kN"), 1)))
    if lat.get("statement"):
        out.append("<p><b>%s</b></p>" % _e(clean(lat["statement"])))
    if ss:
        sa = lat.get("seismic_analysis") or {}
        scale = sa.get("scale")
        sc_txt = ""
        if isinstance(scale, dict):
            sc_txt = " (RSA scaled to VB, IS 1893 7.7.3: %s)" % ", ".join(
                "%s x%s" % (d, _num((v or {}).get("scale") if isinstance(v, dict) else v, 3)) for d, v in scale.items())
        elif scale is not None:
            sc_txt = " (RSA scaled to VB, 7.7.3: %s)" % _num(scale, 3)
        out.append("<p>Seismic (IS 1893 (Part 1):2016 + Amd 1, 2): Z %s, I %s, R %s, soil %s, Ta %s / %s s (%s), Sa/g %s, "
                   "<b>Ah = %s</b>, W = %s kN, <b>VB = %s kN</b>; analysis %s%s.</p>"
                   % (_num(ss.get("Z")), _num(ss.get("I")), _num(ss.get("R")), ss.get("soil"), _f(ss.get("Ta_x_s"), 3), _f(ss.get("Ta_y_s"), 3),
                      _e(clean(ss.get("Ta_formula"))), _num(ss.get("Sa_g")), _num(ss.get("Ah"), 6), _f(ss.get("W_kN"), 1),
                      _f(ss.get("VB_kN") if ss.get("VB_kN") is not None else ss.get("VB_frame_kN"), 2), _e(clean(sa.get("method"))), _e(sc_txt)))
    # ---- 3 combinations ----
    out.append("<h2>3. Load combinations</h2>")
    cc = pkg.get("cfs_combinations") or []
    el_note = (("EL = the elastic IS 1893 (Part 1):2016 base shear of the portal itself (R = 1.0) at factor 1.0 with the IS "
                "801 6.1.2 increase") if portal else B.EL_CFS_NOTE)
    out.append("<p>Cold-formed members -- IS 801 working stress (%d rows, factor 1.0; +33 1/3 %% allowable on the wind / "
               "earthquake rows, IS 801 6.1.2). %s.</p>" % (len(cc), _e(el_note)))
    out.append(_t(["label", "DL", "IL", "Lr", "SL", "WL", "EL", "allowable increase", "basis"],
                  [(c["label"], _num(c["fD"]), _num(c["fL"]), _num(c["fLr"]), _num(c.get("fS", 0)), _num(c["fW"]), _num(c["fE"]),
                    _f(c["allowable_increase"], 4), c.get("row_cite") or c.get("cite")) for c in cc]))
    if not portal:
        out.append("<p>Hot-rolled frame -- IS 800:2007 Table 4 limit-state combinations with the IS 1893 (Part 1):2016 load "
                   "cases, 7.8.2 accidental torsion and IS 800 12.2.3 / IS 18168 overstrength cases: %s combinations "
                   "(listed in the frame report).</p>" % _e(lat.get("load_combinations_n")))
    # ---- 4 lateral system ----
    if portal:
        out.append("<h2>4. Lateral system: all-cold-formed portal frame (IS 801, elastic R = 1.0)</h2>")
    else:
        out.append("<h2>4. Hot-rolled lateral frame (IS 800:2007)</h2>")
    if lat.get("report_html"):
        rel = (os.path.relpath(lat["report_html"], root) if os.path.isabs(lat["report_html"]) else lat["report_html"]).replace(os.sep, "/")
        out.append("<p>Full frame report: <a href='%s'>%s</a> (members, Section 12, connections, bases, drift, irregularity).</p>" % (_e(rel), _e(rel)))
    out.append(_t(["member group", "role", "section", "n", "governing combination", "D/C"],
                  [(m["id"], m["role"], m["section"], m.get("n"), m.get("governing_combo") or "-", _dcf(m.get("DC"))) for m in lat.get("members") or []]))
    conn_rows = []
    for c in lat.get("connections") or []:
        dc = c.get("DC")
        if dc is None and c.get("all_checks_ok"):
            shown = "no ratio: %s (PASS)" % ", ".join(str(x) for x in c.get("check_names") or [])
        else:
            shown = _dcf(dc)
        dem = c.get("value"); cap = c.get("limit")
        force = c.get("units") == "N" and isinstance(dem, (int, float)) and isinstance(cap, (int, float))
        conn_rows.append((c["id"], clean(c["type"]), _kN(dem, 2) if force else "-", _kN(cap, 2) if force else "-", shown,
                          "; ".join(c.get("not_evaluated") or []) or "-"))
    out.append(_t(["connection", "type", "demand (kN)", "capacity (kN)", "D/C", "not evaluated"], conn_rows))
    dt = lat.get("drift_table") or []
    out.append(_t(["storey", "dir", "drift ratio", "limit", "basis", "result"],
                  [(d["storey"], d["dir"], _f(d["drift"], 5), _f(d["limit"], 5), clean(d.get("clause") or d.get("load") or ""), _ok(d["ok"])) for d in dt]))
    cd = lat.get("capacity_design") or {}
    if not portal:
        out.append("<p>IS 800 Section 12 / IS 18168 checks: %s total, <span class='%s'>%s fail</span>, %s not evaluated. Frame "
                   "design status (its own report): <b>%s</b>.</p>"
                   % (cd.get("n_checks"), "fail" if cd.get("n_fail") else "", cd.get("n_fail"), cd.get("n_not_evaluated"),
                      _e(str((lat.get("status") or {}).get("status", "")).upper())))
        ncons = len(lat.get("consistency") or [])
        if ncons:
            out.append("<p class='fail'>The frame report lists %d item(s) to reconcile before it is final; they are carried "
                       "into this report's design status (last chapter).</p>" % ncons)
        if (lat.get("ponding") or {}).get("found"):
            pd_ = lat["ponding"]
            out.append("<p class='note'>Ponding (IS 875 (Part 4):2021 4.4 screen): roof-beam deflection %s mm under the "
                       "impounded load vs the fall %s mm over the half span -- %s (%s).</p>"
                       % (_num(pd_.get("value"), 1), _num(pd_.get("limit"), 1), _ok(pd_.get("ok")),
                          _e(clean((pd_.get("inputs") or {}).get("basis") or pd_.get("cite")))))
    else:
        out.append("<p>%s</p>" % _e(clean(cd.get("note") or "")))
    if (lat.get("status") or {}).get("reasons"):
        out.append("<ul class='note'>" + "".join("<li>%s</li>" % _e(clean(r)) for r in lat["status"]["reasons"][:40]) + "</ul>")
    # ---- 5 CFS members ----
    out.append("<h2>5. Cold-formed members (IS 801:1975 (Reaffirmed 2021) working stress)</h2>")
    out.append("<p class='note'>Moments in kN-m, forces in kN, stresses in MPa, lengths in mm. Each bending and interaction "
               "check states the restraint of its compression flange; with no declared bracing the free flange is "
               "checked unbraced.</p>")
    for m in pkg.get("cfs_members") or []:
        out.append("<h3>%s</h3>" % _e(_member_header(m)))
        lines = []
        fam = m.get("section_family")
        if m.get("auto_selected"):
            a = m["auto_selected"]
            rej = "; ".join("%s (%s kg/m): %s" % (r["section"], _num(r["mass_kg_m"], 2), clean(r["reason"])) for r in a.get("lighter_rejected") or [])
            ref = (" Reference (previous IS 811 section): %s, %s kg/m." % (a["reference_section"], _num(a.get("reference_mass_kg_m"), 2))
                   if a.get("reference_section") else "")
            lines.append("Section auto-selected from family %s: the lightest of %d candidates passing every IS 801 check "
                         "(%d tried), %s kg/m.%s%s" % (a.get("family"), a.get("n_candidates"), a.get("n_tried"),
                                                       _num(m.get("mass_kg_m"), 2), ref,
                                                       (" Lighter sections rejected: " + rej + ".") if rej else ""))
            if a.get("note"):
                lines.append(clean(a["note"]))
        elif fam:
            lines.append("Section: %s (%s), %s kg/m." % (m.get("designator"), clean(fam), _num(m.get("mass_kg_m"), 2)))
        if m.get("material"):
            lines.append("Material: %s." % clean(m["material"]))
        rb = m.get("restraint_basis") or {}
        if rb.get("text"):
            lines.append("Restraint: %s." % clean(rb["text"]))
        elif rb.get("sheeted_text"):
            lines.append("Restraint: %s; %s.%s" % (clean(rb["sheeted_text"]), clean(rb["free_text"]),
                                                  (" Hogging zones: %s." % clean(rb["hogging_text"])) if rb.get("hogging_text") else ""))
        wt = _wind_member_text(m)
        if wt:
            lines.append(wt)
        at = _axial_text(m.get("axial"))
        if at:
            lines.append(at)
        if m.get("zed_basis"):
            lines.append("Zed basis: %s" % clean(m["zed_basis"]))
        if lines:
            out.append("".join("<p class='rs'>%s</p>" % _e(x) for x in lines))
        if m.get("load_table"):
            out.append(_t(["load component", "kN/m2", "kN/m on the member", "applied in"],
                          [(clean(r["component"]), _num(r.get("kNm2"), 3), _num(r.get("kN_per_m"), 3), clean(r.get("applied")))
                           for r in m["load_table"]]))
        trows = []
        for c in m.get("checks") or []:
            un = c.get("units") or ""
            v, vu = _val_units(c.get("value"), un)
            l, _lu = _val_units(c.get("limit"), un)
            res = _ok(c.get("ok")) + (" (info)" if c.get("informational") else "")
            restr = c.get("restraint") if ("bending" in str(c.get("check")) or "interaction" in str(c.get("check"))
                                           or "stability" in str(c.get("check"))) else ""
            trows.append((c.get("combo"), clean(c.get("check")), v, l, vu, _f(c.get("dc")), _f(c.get("allowable_increase"), 3),
                          res, clean(c.get("clause")), short_restraint(clean(restr)) if restr else "-"))
        out.append(_t(["combination", "check", "value", "limit", "unit", "D/C", "increase", "result", "clause",
                       "compression-flange restraint"], trows))
        notes = sorted({clean(c["note"]) for c in m.get("checks") or [] if c.get("note") and ("8.2" in str(c.get("check")) or "sag rod" in str(c.get("check")))})
        if notes:
            out.append("<ul class='note'>" + "".join("<li>%s</li>" % _e(n) for n in notes) + "</ul>")
    # ---- 6 diaphragm ----
    out.append("<h2>6. Diaphragm path to the frame lines</h2>")
    if portal:
        out.append("<p>The roof and wall sheeting of the portal is not relied on as a diaphragm: the longitudinal load goes "
                   "to the cold-formed X-bracing (chapter 4).</p>")
    else:
        out.append("<p class='note'>Unit shear = analysed frame-line reaction / deck length along that line (rigid and "
                   "flexible cases, earthquake and wind enveloped); the governing line is shown. IS 801 9.1.4 excludes "
                   "diaphragms, so every capacity is a cited test / manufacturer value.</p>")
        out.append(_t(["storey", "dir", "F EQ (kN)", "F W (kN)", "governing case", "line (m)", "R (kN)", "deck length (m)",
                       "unit shear (kN/m)", "chord (kN)", "capacity (kN/m)", "capacity source", "result"],
                      [(r["storey"], r["dir"], _kN(r["F_EQ_N"]), _kN(r["F_W_N"]), r.get("governing_case") or r["governing"],
                        _f(r.get("governing_line_m"), 2), _f(r.get("governing_R_kN"), 1), _f(r.get("governing_deck_length_m"), 2),
                        _f(r["v_unit_kN_per_m"], 2), _f(r["chord_force_kN"], 1),
                        _num(r.get("capacity"), 3) if isinstance(r.get("capacity"), (int, float)) else (r.get("capacity") or "not declared"),
                        clean(r.get("capacity_source") or "test / product value required -- VERIFY"),
                        _ok(r.get("ok")) if r.get("demand_evaluated") is not False else "NOT EVALUATED")
                       for r in pkg.get("diaphragm") or [] if r.get("kind") != "collector"]))
        coll = [r for r in pkg.get("diaphragm") or [] if r.get("kind") == "collector"]
        if coll:                                                  # C03: re-entrant collectors
            out.append(_t(["storey", "dir", "re-entrant line", "B_short / B (m)", "collector force (kN)", "capacity (kN)", "result"],
                          [(r["storey"], r["dir"], r.get("line"), "%s / %s" % (_f(r.get("B_short_m"), 2), _f(r.get("B_m"), 2)),
                            _f(r.get("F_collector_kN"), 2), r.get("capacity") or "not declared (design engineer)", _ok(r.get("ok"))) for r in coll]))
    # ---- 7 connections ----
    out.append("<h2>7. Cold-formed connections and anchors (IS 801 7.2 / 7.5)</h2>")
    cn = pkg.get("cfs_connections") or []
    if cn:
        rows = []
        for c in cn:
            dem, cap = c.get("value"), c.get("limit")
            un = c.get("units") or "N"
            rows.append((c["id"], clean(c.get("type")), _val_units(dem, un)[0] if isinstance(cap, (int, float)) else "-",
                         _val_units(cap, un)[0] if isinstance(cap, (int, float)) else "-", _f(c.get("dc")),
                         clean(c.get("governing_check") or "-"), c.get("capacity_basis"), _ok(c.get("ok")), clean(c.get("clause"))))
        out.append(_t(["id", "type", "demand (kN)", "capacity (kN)", "D/C", "governing check", "basis", "result", "clause"], rows))
        for c in cn:
            if c.get("checks") and c.get("id", "").endswith("bolt-group"):
                out.append("<p class='rs'>%s (%s):</p>" % (_e(c["id"]), _e(c.get("governing_combo"))))
                out.append(_t(["check", "value", "limit", "unit", "D/C", "result", "clause"],
                              [(clean(k.get("check")) + (" (detailing)" if k.get("detailing") else ""), _f(k.get("value"), 2),
                                _f(k.get("limit"), 2), "mm" if str(k.get("check")).startswith("7.5.1") else "MPa", _f(k.get("dc")),
                                _ok(k.get("ok")), clean(k.get("clause"))) for k in c["checks"]]))
                if c.get("capacity_components_N"):
                    out.append("<p class='note'>Per-bolt capacity per sheet (kN, IS 801 7.5 with the 6.1.2 increase): %s; the "
                               "most loaded bolt of %s (elastic vector method) is compared with the smallest, times the "
                               "number of sheets.</p>" % (_e(", ".join("%s %.2f" % (k, v / 1e3) for k, v in c["capacity_components_N"].items())),
                                                          _e(c.get("n_bolts"))))
    else:
        out.append("<p>No cold-formed connections are declared for this job: stud-to-track, joist-to-beam clip, purlin cleat "
                   "and board fasteners are the design engineer's details. IS 801:1975 has no screw provisions (7.2 welds, "
                   "7.5 bolts only), so screwed connections are designed from tested or manufacturer values.</p>")
    # ---- 8 durability ----
    out.append("<h2>8. Durability, fire and acoustics</h2>")
    out.append(durability_text(cfg, pkg))
    # ---- 9 grounding ----
    out.append("<h2>9. Grounding (retrieved standards)</h2>")
    out.append(_t(["standard", "used for", "retrieval hits", "status"], pkg.get("grounding") or []))
    # ---- 10 status ----
    out.append("<h2>10. Design status</h2>")
    out.append("<p><b>%s</b> (%s)</p>" % (_e(str(st.get("status", "")).upper()), _e(st.get("authority"))))
    out.append("<ol>" + "".join("<li>%s</li>" % _e(clean(r)) for r in st.get("reasons") or []) + "</ol>")
    out.append("<p class='note'>Software: Steltic CFS India engine (IS 801 / IS 811)%s; engine versions are recorded in "
               "design/calc_package_cfs.json.</p>" % ("" if portal else " with the Steltic hot-rolled IS 800 engine for the frame"))
    out.append("</body></html>")
    path = os.path.join(root, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return path
