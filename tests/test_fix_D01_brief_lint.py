"""D01 brief lint (HR-E-23, HR-A-12, L-14, brief defects B1-B24; rulings R2, R5, R6, R7, R10): the 15 India CFS briefs
in test_buildings/ cite steel IS 1893 Table 9 rows only, never a 'nearest listed city', state the importance factor (the
area rule labelled as owner ruling D8), state k4 and the 6.3.4 class inside the cyclone belt, state the stored goods of
warehouses, k1 for the hospital (Table 1 iv), the one-model / deck-stiffness wording of re-entrant plans, the snow zone
as an EOR map reading, and a numeric across-wind record."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TB = ROOT / "test_buildings"
GLOB = "IN_CFS_Ex*_*.txt"
CYCLONE = {"Ex2", "Ex7", "Ex11"}             # inside the IS 875-3 6.3.4 belt (Chennai, Surat, Visakhapatnam)
REENTRANT = {"Ex6", "Ex7", "Ex8", "Ex9", "Ex10", "Ex11", "Ex12"}     # L / Z / T / U / L-junction / L / cruciform
BANNED = ("rod / angle X-bracing", "vertical irregularity (IS 1893 Table 6, stated)", "Table 8, clinic",
          "Table 8, owner ruling D8", "6.3.4: k4, Kd 1.0")


BRIEFS = sorted(TB.glob(GLOB), key=lambda p: int(re.search(r"_Ex(\d+)_", p.name).group(1)))
IDS = [re.search(r"(Ex\d+)_", p.name).group(1) for p in BRIEFS]


def _id(p):
    return re.search(r"(Ex\d+)_", p.name).group(1)


def _text(p):
    return p.read_text(encoding="utf-8")


def _flat(t):
    return re.sub(r"\s+", " ", t)


def test_all_briefs_found():
    assert len(BRIEFS) == 15, [p.name for p in BRIEFS]


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_steel_table9_rows_only(p):
    """IS 1893 Table 9 i)(a) / i)(b) are the RC OMRF / SMRF rows; steel frames are i)(c) OMRF and i)(d) SMRF."""
    bad = re.findall(r"Table\s*9\s*\(?i\)\s*\(([ab])\)", _flat(_text(p)))
    assert not bad, "%s cites an RC row of Table 9: i)(%s)" % (p.name, bad)


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_no_nearest_city_or_annex_e_map(p):
    t = _flat(_text(p))
    assert not re.search(r"(?i)nearest\s+(listed\s+)?(city|town)", t), p.name       # ruling R5: site_proxy / map only
    assert not re.search(r"(?i)Annex E map", t), p.name                              # the zone map is Fig. 1


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_importance_factor_stated_and_d8_labelled(p):
    """Every brief states I; the area rule is labelled 'owner ruling D8' (ruling R2), never a bare Table 8 (ii)."""
    t = _flat(_text(p))
    assert re.search(r"\bI\s*=\s*1\.[025]\b", t), "%s: importance factor I not stated" % p.name
    for m in re.finditer(r"D8", t):
        assert t[max(0, m.start() - 13):m.start()].endswith("owner ruling "), \
            "%s: 'D8' without 'owner ruling': ...%s" % (p.name, t[max(0, m.start() - 60):m.end() + 10])
    if re.search(r"2,000\s*m", t) and "> 200 persons" not in t.replace("more than 200 persons", "> 200 persons"):
        assert "owner ruling D8" in t, p.name
    assert not re.search(r"Table 8[^.;]{0,15}\(ii\)\s*,\s*D8", t), p.name
    if re.search(r"(?i)\bclinic\b", t):
        assert "owner ruling D8" in t and not re.search(r"Table 8,?\s*clinic", t), p.name


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_cyclone_belt_briefs_state_k4_class(p):
    t = _flat(_text(p))
    inside = bool(re.search(r"(?i)\binside\b.{0,80}?cyclone", t))
    assert inside == (_id(p) in CYCLONE), p.name
    if inside:
        assert re.search(r"k4\s*=\s*1\.(00|15|30)\b", t), "%s: k4 value not stated" % p.name
        assert re.search(r"wind_structure_class\s*=\s*'(post_cyclone|industrial|other)'", t), \
            "%s: 6.3.4 structure class not stated" % p.name
        assert re.search(r"Kd\s*=?\s*1\.0", t), p.name


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_stored_goods_stated(p):
    t = _flat(_text(p))
    if re.search(r"(?i)warehouse|cold-storage", t):
        assert re.search(r"(?i)\bfood\b", t), "%s: stored goods (food / non-food, Table 8 (i)) not stated" % p.name


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_reentrant_briefs_one_model_and_deck_stiffness(p):
    """Ruling R7 + X01: one 3-D model; the brief says which deck stiffness to declare (EOR input) for the Table 5(ii)
    flexible-diaphragm run, and that the job stays PARTIAL without it."""
    t = _flat(_text(p))
    reent = bool(re.search(r"\b[LTUZ]-plan\b|(?i:cruciform)", t)) and not re.search(r"(?i)(separated|split)\b[^.]{0,80}?seismic joint|seismically separated", t)
    assert reent == (_id(p) in REENTRANT), p.name
    if reent:
        assert re.search(r"(?i)\bone (whole-building )?3-D model", t), p.name
        assert "Table 5(ii)" in t and "diaphragm_stiffness" in t and "PARTIAL" in t and "EOR input" in t, p.name


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_snow_zone_as_eor_map_reading(p):
    """Ruling R6: Shimla / Srinagar snow zone Z is an EOR reading of IS 875-4 Fig. 1 (VERIFY), with the altitude."""
    t = _flat(_text(p))
    if re.search(r"Shimla|Srinagar", t):
        assert "EOR map reading of IS 875-4 Fig. 1" in t and "VERIFY" in t, p.name
        assert re.search(r"altitude A = \d,\d{3} m", t), p.name


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_across_wind_needs_numeric_result(p):
    """Ruling R10: 'across-wind declared' is not enough -- the brief names the numeric Mc / Cfs record."""
    t = _flat(_text(p))
    if re.search(r"(?i)across-wind", t):
        assert "Mc_kNm" in t and "Cfs" in t and "R10" in t, p.name


@pytest.mark.parametrize("p", BRIEFS, ids=IDS)
def test_banned_stale_phrases(p):
    t = _flat(_text(p))
    for ph in BANNED:
        assert ph not in t, "%s still says %r" % (p.name, ph)


def test_ex2_scbf_braces_resist_compression():
    """B18: an SCBF brace resists compression (IS 800 12.8, KL/r <= 160); rods cannot."""
    t = _flat(_text(next(p for p in BRIEFS if _id(p) == "Ex2")))
    assert "designed for compression" in t and "KL/r <= 160" in t


def test_ex15_food_storage_importance():
    """B17: cold storage of food -> Table 8 (i) food storage buildings, I = 1.5."""
    t = _flat(_text(next(p for p in BRIEFS if _id(p) == "Ex15")))
    assert "I = 1.5" in t and "food_storage: True" in t
