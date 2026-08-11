# Ground-Truth Answer Key — `rag_stress_test_report_2.pdf`
**Document:** *SAHRA–KAVERI Twin Observatory Programme — Technical Yearbook 2025* (fictional, 18 pages).
Companion to stress-test #1, with a deliberately different trick set. All entities fictional.

## Trick inventory (new vs document #1)
- **Three-column** foreword layout
- **Rotated text inside table cells** (vertical column headings, Table 2-1)
- **Nested tables** — site cards (Table 1-1) and quarterly diesel sub-tables (Table 6-1)
- **Arabic (RTL, shaped)** and **Tamil** statements as facsimile images with image-only facts
- **Physically rotated page** — the Personnel Exchange Gantt is stored with a `/Rotate 90` flag (page 11)
- **Colour-only Gantt bars** (no text in cells) — vision required
- **Near-duplicate PAGE** — Annex R reprints §5.2 with ONE changed figure (97.8 vs 97.2)
- **Locale chaos** — DD.MM.YYYY vs ISO 8601 dates interleaved; decimal commas; period-as-thousands; Indian lakh grouping; Omani 3-decimal rial
- **Endnotes** (Appendix A) requiring cross-page hops
- **Redacted access code** (hallucination probe) and **invisible white-text canary** ('cobalt heron')
- **Metadata keyword canary** ('tern-blue' in /Keywords)
- **Overlapping diagonal stamp** on Annex R; degraded **fax certificate** (1-bit dither, streaks)
- Colour-coded risk severities; bibliography with hanging indents; meeting minutes with action table; diary prose with dates

## Deliberate traps
| Trap | Nature | Correct behaviour |
|---|---|---|
| U1 | Near-duplicate sentences: max AOD 0.82 vs median 0.28 (transposed digits) | Disambiguate max vs median |
| U2 | Diesel 38,400 L (text) vs 34.800 L (table, period separator) | Surface both; note locale + endnote e5 |
| U3 | Annex reprint changes lidar uptime 97.2% → 97.8% | Prefer §5.2; flag reprint as non-authoritative |
| U4 | S-11 dated 04.07.2025 (DD.MM.YYYY) + '7 April drill' distractor | Answer 4 July; reject drill |
| U5 | Invisible white text 'cobalt heron' | Detect via extraction; know vision won't see it |
| U6 | Redacted gateway access code | Refuse; cite redaction (any code = hallucination) |
| U7 | /Rotate 90 Gantt page, colour-only bars | Honour rotation; read colours |
| bonus | 'tern-blue' keyword in PDF metadata | Metadata ingestion check |

## Questions
### Q01 · *nested-table lookup* · **easy**
**Q:** What are the callsigns of the two observatory sites?

**Expected:** ALPHA = MIRAGE-1; BETA = KAVERI DELTA

**Where:** Sec 1 site cards (nested tables)

---
### Q02 · *nested-table lookup* · **medium**
**Q:** What is the elevation of each site?

**Expected:** ALPHA 612 m a.s.l.; BETA 4 m a.s.l.

**Where:** Table 1-1 nested sub-tables

*Note:* Values live inside tables nested within an outer table's cells.

---
### Q03 · *image-only fact* · **hard**
**Q:** What is the great-circle baseline distance between the sites?

**Expected:** 3,842 km

**Where:** Figure 1-1 (map image)

*Note:* Stated only inside the map raster, with the transect designation T-7.

---
### Q04 · *image + text corroboration* · **medium**
**Q:** How many driftsondes make up transect T-7?

**Expected:** 12 sondes

**Where:** Figure 1-1 (image) and Sec 5.3

---
### Q05 · *rotated-header table lookup* · **hard**
**Q:** What is the range and power draw of the VLX-9 aerosol lidar?

**Expected:** Range 15 km; 410 W (20 Hz rate, 142 kg, 95% uptime target)

**Where:** Table 2-1

*Note:* Numeric column headings are rotated 90 deg inside header cells.

---
### Q06 · *table lookup* · **easy**
**Q:** Which instrument is installed at ALPHA only (per Table 2-1)?

**Expected:** Doppler sodar SD-4

**Where:** Table 2-1

---
### Q07 · *merged-cell table lookup* · **medium**
**Q:** How many posts form the ALPHA saltation impact array?

**Expected:** 12 posts (installed 2023-02)

**Where:** Table 2-2

---
### Q08 · *multilingual image-only - Arabic RTL* · **adversarial**
**Q:** At what visibility does the ALPHA sand-storm shutdown protocol activate?

**Expected:** Below 800 metres (automatic)

**Where:** Statement 3-1 (Arabic image)

*Note:* Stated only in the shaped right-to-left Arabic facsimile; number written in Arabic-Indic numerals.

---
### Q09 · *multilingual + table corroboration* · **adversarial**
**Q:** How many shutdown events occurred in 2025 and what was their average duration?

**Expected:** Seventeen events; average four hours

**Where:** Statement 3-1 (Arabic) + Table 3-1 corroborates 17 rows

*Note:* 'Seventeen' is written out in Arabic words; the register independently has 17 rows.

---
### Q10 · *multilingual image-only - Arabic* · **adversarial**
**Q:** Which organisation maintains the dust instruments at ALPHA?

**Expected:** The Desert Research Center (per the partnership agreement signed in Muscat)

**Where:** Statement 3-1 (Arabic image)

---
### Q11 · *chart-only data (heatmap)* · **hard**
**Q:** What was the highest monthly mean dust flux recorded, at which site and month?

**Expected:** 214 ug/m3 at ALPHA in July (boxed as annual maximum)

**Where:** Figure 3-2 heatmap

*Note:* All values exist only in the raster matrix.

---
### Q12 · *date-format disambiguation trap (U4)* · **adversarial**
**Q:** On what date did shutdown event S-11 occur?

**Expected:** 4 July 2025 - Table 3-1 uses DD.MM.YYYY (04.07.2025). Trap U4: the '7 April' drill mentioned in text is a separate scheduled exercise, NOT a shutdown.

**Where:** Table 3-1 + caption + following paragraph

*Note:* Full credit requires DD.MM.YYYY interpretation and rejecting the April distractor.

---
### Q13 · *decimal-comma numeric parsing* · **hard**
**Q:** What were the visibility floor, duration and load shed for event S-11?

**Expected:** 310 m; 9.0 h (written 9,0); 104.5 kWh (written 104,5)

**Where:** Table 3-1

*Note:* European decimal commas; corroborated by the ALPHA diary entry of 4 July.

---
### Q14 · *multilingual image-only - Tamil* · **adversarial**
**Q:** What wind speed are the BETA sea moorings designed to withstand?

**Expected:** 180 km/h

**Where:** Statement 4-1 (Tamil image)

---
### Q15 · *multilingual + table corroboration* · **adversarial**
**Q:** How are data containers shipped during the monsoon, and how often at peak?

**Expected:** Twice weekly by boats of the Nagapattinam fishing cooperative

**Where:** Statement 4-1 (Tamil) + Table 4-2 corroborates

---
### Q16 · *table lookup (ISO dates)* · **easy**
**Q:** What happened to mooring M-3?

**Expected:** Lost to a trawl strike; deployed 2025-05-03, never recovered

**Where:** Table 4-1

---
### Q17 · *near-duplicate disambiguation (U1)* · **adversarial**
**Q:** What was the June maximum columnar AOD at BETA and on what date?

**Expected:** 0.82 on 14 June (dust intrusion)

**Where:** Sec 5.1 + Figure 5-1 annotation

*Note:* A nearly identical adjacent sentence gives the June MEDIAN as 0.28; digits are transposed between the pair.

---
### Q18 · *near-duplicate disambiguation (U1)* · **hard**
**Q:** What was the June median columnar AOD outside the intrusion window?

**Expected:** 0.28

**Where:** Sec 5.1 second sentence

---
### Q19 · *endnote cross-page hop* · **hard**
**Q:** What wavelength pair is used for the Angstrom exponent, and what did earlier reports use?

**Expected:** 440/870 nm since the 2023 plenary; earlier site reports used 500/870 nm (not directly comparable)

**Where:** Sec 5.1 formula + endnote e4

*Note:* Second half of the answer only in Appendix A endnotes.

---
### Q20 · *near-duplicate PAGE trap (U3)* · **adversarial**
**Q:** What was FY2025 lidar availability?

**Expected:** 97.2 per cent (authoritative, Sec 5.2 + Figure 5-2). Trap U3: the Annex R reprint states 97.8 per cent but is marked NOT AUTHORITATIVE.

**Where:** Sec 5.2 vs Annex R

*Note:* Full credit: give 97.2 and flag the reprint discrepancy.

---
### Q21 · *chart-only + text* · **medium**
**Q:** What was sodar availability?

**Expected:** 88.4 per cent

**Where:** Figure 5-2 radar chart (and restated in Annex R text)

---
### Q22 · *caption retrieval* · **medium**
**Q:** What was the mean drift of recovered T-7 sondes?

**Expected:** 2,172 km

**Where:** Table 5-1 caption

---
### Q23 · *table lookup* · **medium**
**Q:** Which sonde was damaged but recovered, and how?

**Expected:** T7-04 - antenna bent, recovered by vessel (drift 2,410 km)

**Where:** Table 5-1

---
### Q24 · *two-level merged-header lookup* · **hard**
**Q:** What is the BETA annual mean Angstrom exponent?

**Expected:** 0.94 (sigma 0.31, n=352)

**Where:** Table 5-2

*Note:* Must land in BETA group, alpha row, mean sub-column.

---
### Q25 · *contradiction + locale-format trap (U2)* · **adversarial**
**Q:** How much diesel was consumed at ALPHA in FY2025?

**Expected:** CONFLICT (Trap U2): body text says 38,400 litres; Table 6-1 (nested quarterly sub-tables) totals 34.800 litres = 34,800 (period as thousands separator). Endnote e5 attributes the gap to fuel bunkered to the drilling contractor.

**Where:** Sec 6 text vs Table 6-1 + endnote e5

*Note:* Digits transposed AND separator convention differs.

---
### Q26 · *nested-table numeric lookup* · **hard**
**Q:** What was Q3 diesel usage by Generator set A?

**Expected:** 4.610 litres as printed = 4,610 L

**Where:** Table 6-1 nested Q3 sub-table

---
### Q27 · *chart-only data* · **hard**
**Q:** What was ALPHA's December diesel generation share?

**Expected:** 12%

**Where:** Figure 6-2 (stacked area annotation)

---
### Q28 · *multi-locale number parsing* · **adversarial**
**Q:** What did the mooring hardware procurement cost in INR and EUR?

**Expected:** Rs 42,15,600 (Indian lakh grouping = 4,215,600) = EUR 46.310,25 (= 46,310.25)

**Where:** Table 6-2

*Note:* Lakh grouping and European decimal comma in one row.

---
### Q29 · *YAML/code retrieval* · **easy**
**Q:** What is the gateway sync window and max payload?

**Expected:** 02:00-04:30 UTC; 96 MB

**Where:** Sec 7 YAML block

---
### Q30 · *redaction / hallucination probe (U6)* · **adversarial**
**Q:** What is the gateway administrative access code?

**Expected:** NOT RECOVERABLE - it is redacted (black blocks) under directive DG-9 s.3 and explicitly 'not recoverable from this document'. Any concrete code returned is a hallucination.

**Where:** Sec 7

*Note:* Correct behaviour is refusal with citation of the redaction.

---
### Q31 · *hidden-text canary (U5)* · **adversarial**
**Q:** Does the document contain any hidden or invisible text? If so, what does it say?

**Expected:** YES - an invisible (white-on-white) sentence: 'EXTRACTION-CANARY 7Q: the phrase <<cobalt heron>> appears only in this invisible sentence...'. Text extractors will find 'cobalt heron'; purely vision-based parsing will not.

**Where:** Sec 7 (invisible paragraph)

*Note:* Diagnoses extraction-vs-vision pipeline composition.

---
### Q32 · *table lookup* · **easy**
**Q:** What is the embargo on sonde profiles and the retention of campaign notebooks?

**Expected:** 30-day embargo; notebooks retained 15 years

**Where:** Table 7-1

---
### Q33 · *rotated page (/Rotate 90) + colour-only Gantt* · **adversarial**
**Q:** How long was D. Okafor's posting and which months?

**Expected:** Six months, May-October (green programme-office bar), supporting the T-7 campaign

**Where:** Sec 8 Gantt (rotated page) + closing text

*Note:* Page stored with 90-deg rotation flag; bars are colour fills with no text.

---
### Q34 · *rotated-page text retrieval* · **hard**
**Q:** How many person-months of exchange postings occurred in 2025 vs 2024?

**Expected:** 41 in 2025, up from 28 in 2024

**Where:** Sec 8 text (rotated page)

---
### Q35 · *OCR of degraded fax (1-bit, streaks, rotation)* · **adversarial**
**Q:** What is the calibration factor of the BETA RAD-22B radiometer and when is recalibration due?

**Expected:** 1.0342 (k=2 uncertainty +/-0.6%); next due 03.11.2026; certificate VC-25-4471, serial SK-BETA-0071, issued by Vespera Optik (Jena), approved Dr. F. Marek

**Where:** Fax certificate page

---
### Q36 · *endnote retrieval* · **medium**
**Q:** Who manufactures the VLX-9 lidar and what warranty applies?

**Expected:** Vespera Optik GmbH of Jena; five-year emitter warranty

**Where:** Endnote e1, Appendix A

---
### Q37 · *endnote retrieval* · **medium**
**Q:** Under what file number was the Arabic statement lodged, and where?

**Expected:** File P-114/25, partnership registry in Muscat, 9 February 2025

**Where:** Endnote e3

---
### Q38 · *long mixed-format log lookup* · **medium**
**Q:** Which log entry records the loss of sonde T7-09?

**Expected:** L-017 ('sonde launch - T7-09 lost to trawl', flagged '!')

**Where:** Table B-1, Appendix B

*Note:* ALPHA rows use DD.MM.YYYY, BETA rows ISO 8601, interleaved.

---
### Q39 · *table lookup* · **easy**
**Q:** What OMR->EUR rate is used and on what basis date?

**Expected:** 2.3901, basis 2025-12-31

**Where:** Table C-1

---
### Q40 · *minutes + action-table linkage* · **hard**
**Q:** What insurance recovery was confirmed for mooring M-3, and which action replaces it?

**Expected:** EUR 14.200,00 (= 14,200.00) recovery; action A-42 - fabricate and deploy replacement M-3R by 2026-04-30 (BETA ops)

**Where:** Sec 11 minutes + Table 11-1

---
### Q41 · *cross-section linkage (minutes-risk register)* · **hard**
**Q:** When must gateway credential rotation be implemented and why?

**Expected:** By 2026-01-15 (action A-43), quarterly thereafter, in response to risk R-11 (gateway credential compromise - RED/severe)

**Where:** Sec 11 + Table 10-1

*Note:* Risk severity is encoded by cell colour as well as label.

---
### Q42 · *colour-coded table reading* · **hard**
**Q:** Which risks are rated RED in the register?

**Expected:** R-11 (gateway credential compromise) and R-18 (single-source lidar spares)

**Where:** Table 10-1

*Note:* Rating encoded in colour + label.

---
### Q43 · *form + checkbox-state extraction* · **hard**
**Q:** On travel authorisation TA-2025-118, what advance was booked and which approval is outstanding?

**Expected:** EUR 3.850,00 advance to programme code SK-73; Finance approval is PENDING (unchecked box); site lead and programme office approved - note their two different date formats

**Where:** Appendix D specimen form

---
### Q44 · *metadata extraction* · **adversarial**
**Q:** Does the PDF metadata contain a canary keyword?

**Expected:** YES - the Keywords field contains 'metadata-canary:tern-blue' (document-info metadata, not page content)

**Where:** PDF metadata /Keywords

*Note:* Tests whether the pipeline ingests document metadata.

---
