# Example briefs -- steltic CFS India (D3 / D5 / L7)

The 15 India briefs below are the programme's test buildings. Each keeps its site, geometry, occupancy and loads; the
lateral system is the hot-rolled IS 800 Section 12 frame ruled by zone (II OCBF R 4.0; III-V SCBF R 4.5; EBF R 5.0; a hot-rolled
SMF portal where the brief says so and h < 15 m). Cold-formed members (IS 801:1975 working stress, IS 811:1987 sections) are
gravity / wind members only. Ex5 (Hyderabad) is the one all-CFS lateral case, designed elastically (R = 1.0 stated).

| Brief | System |
|---|---|
| `IN_CFS_Ex1_SCBF_4levels_Delhi.txt` | SCBF R 4.5 (fixture `tests/fixtures/IN_CFS_Ex1`) |
| `IN_CFS_Ex2_HR_SMF_portal_Chennai_wind.txt` | hot-rolled SMF portal + CFS secondaries, cyclone belt |
| `IN_CFS_Ex3_SCBF_5levels_Mumbai.txt` | SCBF R 4.5 |
| `IN_CFS_Ex4_OCBF_6levels_Bengaluru.txt` | OCBF R 4.0 |
| `IN_CFS_Ex5_Portal_allCFS_elastic_Hyderabad.txt` | all-CFS portal, elastic R 1.0 (fixture `tests/fixtures/IN_CFS_Ex5`) |
| `IN_CFS_Ex6_SCBF_5levels_Lplan_Pune.txt` | SCBF R 4.5, L-plan 3-D |
| `IN_CFS_Ex7_SCBF_6levels_Zplan_Surat.txt` | SCBF R 4.5, cyclone belt |
| `IN_CFS_Ex8_SCBF_4levels_Tplan_Ahmedabad.txt` | SCBF R 4.5, T-plan 3-D |
| `IN_CFS_Ex9_SCBF_podium_5over2_Uplan_Noida.txt` | SCBF R 4.5 continuous through the podium (no two-stage) |
| `IN_CFS_Ex10_OCBF_highbay_2levels_Nagpur.txt` | OCBF R 4.0 (+ SMRF bay at the open front if used) |
| `IN_CFS_Ex11_OCBF_3levels_coastal_Vizag.txt` | OCBF R 4.0, cyclone belt |
| `IN_CFS_Ex12_SCBF_8levels_crossplan_Kolkata.txt` | SCBF R 4.5, RSA |
| `IN_CFS_Ex13_SCBF_4levels_Lucknow.txt` | SCBF R 4.5 |
| `IN_CFS_Ex14_SCBF_clinic_splitlevel_Coimbatore.txt` | SCBF R 4.5, I = 1.2 |
| `IN_CFS_Ex15_HR_SMF_portal_coldstorage_Srinagar.txt` | hot-rolled SMF portal + EBF longitudinal, snow, Zone V |

The full site / zone / R / clause table is `scratch/CFS/SYSTEM_TABLE.md` (programme scratch).

Agents LIVE-retrieve IS 875 / IS 1893 into `cfg['load_plan']` every job; IS 800 / IS 18168 only with the allowlisted purpose;
no AISI / ASCE / AISC / SFIA. The former US briefs, the `IN_CFS_ExN_EOR_inputs_EXAMPLE.json` fixtures (wall vn / EOR R
companions of the removed wall path) and the original India briefs are kept under `usa_reference/` and are not used.
