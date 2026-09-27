# India CFS RAG collection → corpus stem map

Canonical map: `steltic/india_collections.py` (mirrored in `steltic/india_collection_stems.json`). Corpus: your IS corpus, built in the Steltic hub from your own licensed BIS PDFs (see CORPUS_FIX_LLM_INSTRUCTIONS.md)
(`$INDIA_CORPUS_ROOT`, served at `RAG_API_URL`).

| collection= (`engineering_standards_` or `engineering_standard_` prefix) | stem | use |
|---|---|---|
| `…_IS801` | `IS_801_1975` | CFS member design (primary) |
| `…_IS811` | `IS_811_1987` | CFS section properties |
| `…_IS811_Amd1` | `IS_811_1987_Amd1_2011` | may index 0 sections → `found:false` |
| `…_IS875_P1` … `…_IS875_P5` | `IS_875_Part_1_2026` … `IS_875_Part_5_1987` | loads, mandatory every job |
| `…_IS1893` / `…_IS1893_P1` | `IS_1893_Part_1_2016` | seismic, mandatory every job |
| `…_IS800` | `IS_800_2007` | GATED: hot-rolled lateral frame (`purpose = lateral_frame_is800`) or Table 6 (`serviceability_limits_table6`) |
| `…_IS18168` | `IS_18168_2023` | GATED: same purposes (Zone IV / V braced frames) |

Load collections (IS875_P* + IS1893) are **mandatory every job** before writing `cfg['load_plan']`.
IS 800 / IS 18168 without an allowlisted `purpose` are refused by `india_cfs_gates.gate_is800_query` (C6).
No worked-example collection is ingested for India (`cfs_design_examples` is not available; see DESIGN_EG_INDEX.md).

`job_tools._collection_stem()` posts `stem` / `doc` on the RAG payload so the hosted registry can resolve India corpus aliases.

Never point this agent at the USA corpus (`/workspace/engineering_rag`) or at AISI / ASCE / AISC collections.
