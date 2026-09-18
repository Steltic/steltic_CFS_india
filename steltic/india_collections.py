"""Map agent RAG collection names → India CFS corpus document stems.

Corpus root: /workspace/engineering_rag_india (stem files under documents/standards/<STEM>/).
Hosted rag_server may register collections as engineering_standards_IS*; this map is the
canonical translation for local aliases, escalation, and docs.

CFS design: IS 801 / IS 811 (+ Amd1). Loads: IS 875 Parts 1–5 + IS 1893 Part 1.
Do NOT map HR-only IS 808 shape catalogs here as primary CFS design authority.
"""
from __future__ import annotations

COLLECTION_TO_STEM: dict[str, str] = {
    # CFS design
    "IS801": "IS_801_1975",
    "IS_801": "IS_801_1975",
    "IS811": "IS_811_1987",
    "IS_811": "IS_811_1987",
    "IS811_Amd1": "IS_811_1987_Amd1_2011",
    "IS_811_Amd1": "IS_811_1987_Amd1_2011",
    # Loads — mandatory every job
    "IS875_P1": "IS_875_Part_1_2026",
    "IS875_PART1": "IS_875_Part_1_2026",
    "IS_875_P1": "IS_875_Part_1_2026",
    "IS875_P2": "IS_875_Part_2_1987",
    "IS875_PART2": "IS_875_Part_2_1987",
    "IS_875_P2": "IS_875_Part_2_1987",
    "IS875_P3": "IS_875_Part_3_2015",
    "IS875_PART3": "IS_875_Part_3_2015",
    "IS_875_P3": "IS_875_Part_3_2015",
    "IS875_P4": "IS_875_Part_4_1987",
    "IS875_PART4": "IS_875_Part_4_1987",
    "IS_875_P4": "IS_875_Part_4_1987",
    "IS875_P5": "IS_875_Part_5_1987",
    "IS875_PART5": "IS_875_Part_5_1987",
    "IS_875_P5": "IS_875_Part_5_1987",
    "IS1893": "IS_1893_Part_1_2016",
    "IS_1893": "IS_1893_Part_1_2016",
    "IS1893_P1": "IS_1893_Part_1_2016",
    "IS1893_PART1": "IS_1893_Part_1_2016",
}

for _k, _v in list(COLLECTION_TO_STEM.items()):
    COLLECTION_TO_STEM[f"engineering_standards_{_k}"] = _v

for _k, _v in list(COLLECTION_TO_STEM.items()):
    if _k.startswith("engineering_"):
        continue
    COLLECTION_TO_STEM.setdefault(f"engineering_standards_{_k}", _v)
    COLLECTION_TO_STEM.setdefault(f"engineering_standard_{_k}", _v)

STEM_TO_COLLECTION: dict[str, str] = {
    "IS_801_1975": "engineering_standards_IS801",
    "IS_811_1987": "engineering_standards_IS811",
    "IS_811_1987_Amd1_2011": "engineering_standards_IS811_Amd1",
    "IS_875_Part_1_2026": "engineering_standards_IS875_P1",
    "IS_875_Part_2_1987": "engineering_standards_IS875_P2",
    "IS_875_Part_3_2015": "engineering_standards_IS875_P3",
    "IS_875_Part_4_1987": "engineering_standards_IS875_P4",
    "IS_875_Part_5_1987": "engineering_standards_IS875_P5",
    "IS_1893_Part_1_2016": "engineering_standards_IS1893",
}

INDIA_CORPUS_ROOT = "/workspace/engineering_rag_india"
INDIA_ALIASES_FILE = f"{INDIA_CORPUS_ROOT}/indexes/aliases.json"

LOAD_COLLECTIONS = [
    "engineering_standards_IS875_P1",
    "engineering_standards_IS875_P2",
    "engineering_standards_IS875_P3",
    "engineering_standards_IS875_P4",
    "engineering_standards_IS875_P5",
    "engineering_standards_IS1893",
]

DESIGN_COLLECTIONS = [
    "engineering_standards_IS801",
    "engineering_standards_IS811",
    "engineering_standards_IS811_Amd1",
]


def normalize_collection(name: str) -> str:
    if not name:
        return name
    raw = str(name).strip()
    stem = stem_for_collection(raw)
    if stem and stem in STEM_TO_COLLECTION:
        return STEM_TO_COLLECTION[stem]
    return raw


def stem_for_collection(name: str) -> str | None:
    if not name:
        return None
    key = str(name).strip()
    if key in COLLECTION_TO_STEM:
        return COLLECTION_TO_STEM[key]
    low = key
    if low.lower().startswith("engineering_standards_"):
        low = key[len("engineering_standards_"):]
    return COLLECTION_TO_STEM.get(low) or COLLECTION_TO_STEM.get(low.upper()) or COLLECTION_TO_STEM.get(low.replace("-", "_"))


def is_india_spec_collection(name: str) -> bool:
    c = (name or "").lower()
    if "opensees" in c or "example" in c:
        return False
    if stem_for_collection(name):
        return True
    return "engineering_standard" in c or any(
        t in c for t in ("is801", "is811", "is875", "is1893", "aisi", "s100", "s240", "s400", "asce")
    )
