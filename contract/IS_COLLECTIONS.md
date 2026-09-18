# India CFS RAG collection → corpus stem map

Canonical map: `steltic/india_collections.py`. Corpus: `/workspace/engineering_rag_india`.

| collection= (either `engineering_standards_` or `engineering_standard_` prefix) | stem |
|---|---|
| `…_IS801` | `IS_801_1975` |
| `…_IS811` | `IS_811_1987` |
| `…_IS811_Amd1` | `IS_811_1987_Amd1_2011` |
| `…_IS875_P1` … `…_IS875_P5` | `IS_875_Part_1_2026` … `IS_875_Part_5_1987` |
| `…_IS1893` / `…_IS1893_P1` | `IS_1893_Part_1_2016` |

Load collections (IS875_P* + IS1893) are **mandatory every job** before writing `cfg['load_plan']`.

`job_tools._collection_stem()` posts `stem` / `doc` on the RAG payload so the hosted registry
can resolve India corpus aliases without re-hardcoding formulas.

Never point this agent at the USA corpus (`/workspace/engineering_rag`).
