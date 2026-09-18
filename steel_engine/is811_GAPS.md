# IS 811:1987 section catalog — gaps

**Source:** `pdftotext -layout` of IS_811_1987.pdf + RAG `indexes/tables.json`.
**Output:** `is811_shapes.csv` (390 rows) + `is811_catalog.json`.
**Skipped/unreadable lines:** 32

## Ingested (found:true)
- Tables 1–10: EA, UA, CWS, CWR, CLS, CLR, HS, HRH, HRB, LZ

## Counts by Type
- CLR: 65
- CLS: 18
- CWR: 84
- CWS: 27
- EA: 21
- HRB: 3
- HRH: 12
- HS: 21
- LZ: 121
- UA: 18

## found:false / deferred
- **Table 11** (90° corner): not a framing member — use RAG when needed; not in CSV.
- **IS_811_1987_Amd1_2011**: 0 indexed tables/sections — found:false for Amd1 property deltas.
- **OCR nits**: letter/digit swaps skip rows failing mass/area sanity (listed below).
- **Cw / J / x0 / Ixy**: not always recovered from layout OCR — A/Ix/Iy prioritized; RAG-cite remainder.
- **Effective width / IS 801 capacities**: out of scope (properties only).

## RAG table extract inventory: 28 chunks for IS_811_1987

## Skipped line sample (first 40)
- L501 T1: short_desig :: '30 x 30 x I.60   30     I.60       2.40   0.710     0.905     0.834     0.834          0.814        '
- L509 T1: props_unreadable :: ' 40X40X2.00'
- L510 T1: props_unreadable :: ' 40 X 40 x 2.55'
- L511 T1: props_unreadable :: ' 40 x 40 x 3.15'
- L555 T1: short_desig :: ' 50 X 50 ,X 2.00    50   2.00    3.00   I.50      I.91   1.36    1.36       4.83       7.84     1.82'
- L701 T3: short_desig :: '  30 x 30 x ;.OO     30     2.00   3.00    1.28    1.63    1.13     2.46      1.51    1.23   0.964  '
- L902 T5: short_desig :: '30x30x10x_l.60       30   10      1.60   2.40   1.21       1.54   1’35   2.19   1.85    1.19    1.10'
- L906 T5: props_unreadable :: '40x40x10x1.60        40   10             2.40              202    1 70   5.50   4.24    1.65    1.45    2.75    1.84    '
- L907 T5: props_unreadable :: '40X40X 15x2.00       40   15     :::     3.00   iii        2:66   1:u    6.63   5.87    1.58    1.49    3.32    2.74    '
- L963 T6: props_unreadable :: '    50X25X15X2.00         50   25      15        2.00   3.00    1.17      2.26    1.05             7.19        2.08     '
- L966 T6: short_desig :: '    50 X 40 x I5 x 2.00   50   40      15        2.00   3.00    2.24      2.86    1.73            11'
- L978 T6: props_unreadable :: '     70X25X    10x 1.60     70   25   10    1.60   2.40    1.59   2.02    0.787     14.2    1.65   2.66    1.903    4.07'
- L986 T6: short_desig :: '     80 X 40 x IO X 1.60    80   40   10    1.60   2.40    2.09    2.66    1.31     27.0    5.51   3'
- L1007 T6: short_desig :: '    100X60X    lSX2.00     100   60    I5   2.00   3.00    3.66    4.66   2.13      76.9   22.6    4'
- L1012 T6: short_desig :: '    120x50x2Qx3.15         120   50   20    3.15   4.73    5.76    7.34    1.70    155     24.7    4'
- L1016 T6: short_desig :: '    1200606025X4.00        120   60   25    4.00   6.00    8.02   10.2     2.23    216     50.7    4'
- L1096 T7: short_desig :: '  30 x 30 x ib 2 1.25     30   10      1.25     1.88     0.974          1.24          1.36      1.55'
- L1098 T7: short_desig :: '  35 X 35 X IO X 1.25     35   10      1.25     1.88     1.12           1.43          1.53      2.40'
- L1102 T7: short_desig :: '  40X40X    ISX2.00       40   I5      2.00     3.00     2.08           2.66          1.86      5.87'
- L1142 T8: props_unreadable :: '     50 x 40 x 10 x 1350    50   40       IO   1.60    2.40     1.84    2.34    2.17      7.40        7.72     1.78     '
- L1152 T8: short_desig :: '     80 X 50 X I5 X 2.00    80   50       I5   2.00    3.00     3.50    4.46    3.65     35.6       '
- L1179 T9: short_desig :: '30X 50x IO x I.25     30   50      IO        I.25   1.88    I.17     I .49      I.14         1.90   '
- L1182 T9: short_desig :: '40X50X     IOX 1.60   40   50      IO        I.60   2.40    I.71     2.18       1.58         4.62   '
- L1183 T9: short_desig :: '40X 60X I5 X 2.00     40   60      I5        2.00   3.00    2.40     3.06       1.63         6.95   '
- L1222 T10: short_desig :: '85X40X20X    l&l        2.40   3.06    33.6       14.2          43.0     4.80    1.25    0.5ii    7.'
- L1228 T10: props_unreadable :: '90X40x20X2.00           3.03   3.86    46.5       17.0          51.5     5.95    1.24    0.521   10.3       4.35      10'
- L1236 T10: props_unreadable :: '  90x40x20x2.30          3.43   4.38    52.1    18.8    64.3    6.60    1.23    0.518   II.6    4.84   11.6    2.84   23'
- L1244 T10: short_desig :: ' 100x40x20x       I.60   2.59   3.30    49.4    14.2    58.3     5.31   1.27    0.450    9.88   3.63'
- L1254 T10: short_desig :: ' 110X45X20X       I.60   2.84   3.62    66.7    19.2    78.8     7.10   1.40    0.450   12.1    4.34'
- L1269 T10: short_desig :: ' 125X45X20X       I.60   3.03   3.86    90.3    19.2   102       7.63   1.41    0.374   14.4    4.34'
- L1399 T10: props_unreadable :: '    270 x 75 X 20 X 2.30    1.95   10.1    1060        98.3      1110       46.3    2.14     0.227      78.3     13.3   '
- L1407 T10: props_unreadable :: '    290X75X20X      1.60    5.86    1.46    895        72.1       932       35.0    2.16     0.208      61.7      9.72  '

## Units
Pipeline kip+inch. CSV converts from IS 811 SI (cm²/cm⁴/mm); `*_si_*` retained.

## Dual-path lookup
`cfs_sections.props` / `gross_props`: IS 811 labels first; SFIA designators remain twin geometry.

## Clause anchors (RAG / markdown)
- 7.1 dimensions → Tables 1–10 (found:true)
- 7.2 mass & properties → Tables 1–10 (found:true)
- 7.2.3 Ri = 1.5 t (found:true)
