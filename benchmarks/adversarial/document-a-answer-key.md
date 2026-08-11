# Ground-Truth Answer Key — `rag_stress_test_report.pdf`
**Document:** *Meridian Trench Research Consortium — Annual Report FY2025* (fully fictional, 19 pages).
All entities, people, vessels and numbers are invented so a RAG pipeline cannot answer from the LLM's parametric knowledge — every correct answer requires actual retrieval (and for several questions, vision/OCR).

## How to use
1. Ingest the PDF into your pipeline.
2. Ask each question verbatim (or paraphrased, for robustness testing).
3. Score against `expected_answer`. Suggested scoring: exact-match for numerics/IDs, semantic match for prose, and for the four *adversarial contradiction* questions award full credit only when the answer surfaces the conflict.

## Deliberate traps
| Trap | Nature | Locations | Correct behaviour |
|---|---|---|---|
| T1 | Station depth 5,120 m vs 5,210 m | Exec Summary vs Sec 1 / Table 1-1 / Table B-1 | Prefer 5,210 m (certified); flag conflict. Note the numeric collision with EUR 5,120k in Table 6-1. |
| T2 | 'Fourteen' Q3 dives vs 16 table rows | Sec 3 text vs Table 3-1 | Surface both; flag conflict |
| T3 | Near-duplicate paragraphs: juvenile 4.2 m vs mature 6.8 m | Sec 4.2 | Disambiguate by life stage |
| T4 | Total spend EUR 47.2 M vs EUR 45.8 M | Exec Summary vs Table 6-1 | Surface both; flag conflict |
| T5 | 1998 depth 5,340 m vs modern 5,210 m | Scanned memo vs Table B-1 | Explain historical revision (uncorrected single-beam vs multibeam 2023) — not an error |

## Feature inventory (what the PDF exercises)
- Cover with hyperlink; auto-generated **TOC** with dot leaders (p. 2)
- **Two-column** layouts: Executive Summary (p. 3) and Appendix A glossary
- **Merged-cell tables**: roster (Table 2-1), multi-level financial header (Table 6-1), grouped constants (Table B-1)
- **46-row dive log spanning pages** with repeated header, blank cells, em-dashes, accounting negatives '(12)'
- **Sentence split across a page break** ('...to avoid | birdcaging...')
- **Charts whose data exists only as pixels**: bar (Fig 4-2), line (Fig 4-3), pie (Fig 6-1)
- **Diagrams with embedded text**: station layout (Fig 1-1), org chart (Fig 2-1)
- Rendered **formula image** (O2 saturation) + markup formula (P = P0 + rho g h)
- **Code blocks**: Python constants, C CRC-16, JSON pipeline config
- **Footnotes** with superscript markers (Secs 2 and 4)
- **Five languages**: Japanese (embedded subset font), German, French, Russian, Hindi (as image, Devanagari)
- **Landscape fold-out** incident table (p. 12); **rotated margin text** and diagonal **watermark** on every main page
- **Simulated 1998 scan**: rotation, noise, blur, coffee ring, scan lines (p. 13)
- **Form page** with checked/unchecked ballot boxes (Sec 9)
- **Cross-references** (Sec 4.3 -> Table B-1), internal anchors, PDF metadata (title/author/subject)

## Questions
### Q01 · *prose retrieval* · **easy**
**Q:** What is the name of the consortium's deep-sea research station?

**Expected:** HALCYON DEEP

**Where:** Exec Summary; Sec 1

---
### Q02 · *prose retrieval* · **easy**
**Q:** Which submersible completed all crewed sorties in FY2025?

**Expected:** Nereid-2

**Where:** Sec 3 opening

---
### Q03 · *prose retrieval (numeric)* · **easy**
**Q:** What operational availability did the station achieve in FY2025?

**Expected:** 96.4 per cent

**Where:** Exec Summary

---
### Q04 · *table lookup* · **easy**
**Q:** What is the hull design pressure of the station and which body certified it?

**Expected:** 62 MPa, certified by Bureau Abyssal International (BAI), valid to 2031-06

**Where:** Table 1-1

---
### Q05 · *table lookup under merged cell* · **medium**
**Q:** How many FTE tether and winch technicians are on the roster?

**Expected:** 3

**Where:** Table 2-1 (Dive Operations group)

*Note:* Department cell is vertically merged; row inherits 'Dive Operations'.

---
### Q06 · *footnote retrieval* · **medium**
**Q:** From which partner is the ROV supervisor post seconded?

**Expected:** The Kaiyu-7 operating partner (Japanese partner, see Sec 7.1)

**Where:** Footnote 1, Sec 2

---
### Q07 · *long-table row lookup* · **medium**
**Q:** For dive D-2025-018, state the pilot, max depth, duration and samples taken.

**Expected:** Pilot L. Fernandez; 5,204 m; 6:42; 9 samples (date 15 Apr, objective Tether inspection)

**Where:** Table 3-1

*Note:* Table spans multiple pages with repeated header.

---
### Q08 · *aggregation across page-spanning table* · **hard**
**Q:** How many dives in total are recorded in the FY2025 dive log?

**Expected:** 46

**Where:** Table 3-1 (all rows) / caption

*Note:* Caption states 46; counting rows across pages must also give 46.

---
### Q09 · *contradiction trap* · **adversarial**
**Q:** How many crewed dives took place in the third quarter of 2025?

**Expected:** CONFLICT (Trap T2): narrative says 'fourteen crewed dives'; Table 3-1 contains 16 rows dated Jul-Sep. Ideal answer surfaces both and flags the discrepancy.

**Where:** Sec 3 text vs Table 3-1

*Note:* Score full marks only if both values are surfaced.

---
### Q10 · *sentence split across page boundary* · **hard**
**Q:** After dive D-2025-042, what failure mode was the reduced-speed tether rewind intended to avoid?

**Expected:** Birdcaging of the armoured strands

**Where:** Sec 3 closing paragraph

*Note:* The sentence breaks mid-clause across a page break; naive per-page chunking severs question from answer.

---
### Q11 · *chart-only data (vision/OCR)* · **hard**
**Q:** How many Mollusca specimens were catalogued in FY2025?

**Expected:** 149

**Where:** Figure 4-2 (bar chart)

*Note:* Value exists ONLY inside the raster chart; not in any text.

---
### Q12 · *chart-only data (vision/OCR)* · **hard**
**Q:** What was the water temperature at 3,000 m on CTD cast MT-25-118?

**Expected:** 2.4 deg C

**Where:** Figure 4-3 (line chart annotation)

*Note:* Annotated only on the chart image.

---
### Q13 · *near-duplicate disambiguation (Trap T3)* · **adversarial**
**Q:** What length do mature colonies of Apolemia spectra reach?

**Expected:** 6.8 metres

**Where:** Sec 4.2, second paragraph

*Note:* A nearly identical paragraph gives 4.2 m for JUVENILE colonies; retrieval must pick the mature variant.

---
### Q14 · *near-duplicate disambiguation (Trap T3)* · **hard**
**Q:** On how many occasions were juvenile Apolemia spectra colonies observed?

**Expected:** Eleven

**Where:** Sec 4.2, first paragraph

*Note:* Mature colonies: three occasions (distractor).

---
### Q15 · *footnote retrieval* · **medium**
**Q:** Under what submission number and date were the new-species files lodged with the Registry of Hadal Taxa?

**Expected:** #RHT-2025-0917, on 4 December 2025

**Where:** Footnote 3, Sec 4.1

---
### Q16 · *formula context retrieval* · **medium**
**Q:** What hydrostatic pressure results at station depth using P = P0 + rho*g*h?

**Expected:** Approximately 53.4 MPa

**Where:** Sec 4.3 (also Sec 1)

*Note:* Formula P = P0 + rho g h given in text markup; O2 equation is an image.

---
### Q17 · *code block retrieval* · **medium**
**Q:** What is the value of DEPTH_ALARM_M in the ctd9d firmware?

**Expected:** 5300 (metres)

**Where:** Sec 5.1 code block

*Note:* Exists only inside the Python-style code listing.

---
### Q18 · *code block retrieval* · **medium**
**Q:** Which CRC polynomial does the winch controller firmware use?

**Expected:** 0x1021 (CRC-16/CCITT)

**Where:** Sec 5.2 code block

---
### Q19 · *nested list retrieval* · **medium**
**Q:** What is the maximum permitted clock skew to the surface in the pre-dive checklist?

**Expected:** Less than 40 ms

**Where:** Sec 5.3 nested checklist

---
### Q20 · *multi-level merged-header table lookup* · **hard**
**Q:** What was the FY2025 ACTUAL expenditure on Research Programmes?

**Expected:** EUR 8,660 thousand (8.66 million)

**Where:** Table 6-1

*Note:* Must resolve the 'Actual' column nested under the 'FY2025' spanned header, not FY2024.

---
### Q21 · *contradiction trap* · **adversarial**
**Q:** What was total consortium expenditure in FY2025?

**Expected:** CONFLICT (Trap T4): Exec Summary says audited EUR 47.2 million; Table 6-1 total is EUR 45,800 thousand (45.8 million). Ideal answer surfaces both.

**Where:** Exec Summary vs Table 6-1

---
### Q22 · *chart-only data (vision/OCR)* · **hard**
**Q:** What percentage of FY2025 expenditure went to Vessel Operations?

**Expected:** 35%

**Where:** Figure 6-1 (pie chart)

*Note:* Percentages appear only in the pie image.

---
### Q23 · *multilingual retrieval - Japanese* · **hard**
**Q:** What is the rated diving depth of the Kaiyu-7 ROV?

**Expected:** 6,500 m

**Where:** Sec 7.1 (Japanese text)

*Note:* Fact stated only in Japanese; also written in kanji numerals.

---
### Q24 · *multilingual retrieval - German* · **medium**
**Q:** What operating pressure are the second-generation titanium pressure housings rated for, and when were they handed over?

**Expected:** 62 MPa; handover on 11 March 2025 in Bremerhaven

**Where:** Sec 7.2 (German text)

---
### Q25 · *multilingual retrieval - French* · **medium**
**Q:** How many sonar arrays did the French institute supply, and what is the model name and nominal range?

**Expected:** Three arrays; model 'Echo-Marin 9'; nominal range 1,800 m each

**Where:** Sec 7.3 (French text)

---
### Q26 · *multilingual retrieval - Cyrillic* · **medium**
**Q:** What is the name and ice class of the Russian supply vessel?

**Expected:** 'Severnaya Zvezda' (Northern Star); ice class Arc5; four voyages in the year

**Where:** Sec 7.4 (Russian text)

---
### Q27 · *multilingual + image-only (Devanagari OCR)* · **adversarial**
**Q:** During the monsoon period, how often is surface resupply possible?

**Expected:** Once every six weeks (June-September); reserves held at minimum twelve weeks; Chennai-based partner operates the vessel

**Where:** Sec 7.5 (Hindi facsimile image)

*Note:* The Hindi statement is a raster image; requires vision/OCR plus Hindi comprehension.

---
### Q28 · *landscape/rotated page table lookup* · **hard**
**Q:** What part number caused the Wet Porch flooding incident IR-2025-04, and how much downtime resulted?

**Expected:** Failed penetrator seal P/N HX-1147; 62 hours downtime

**Where:** Table 8-1 (landscape page)

*Note:* Page is landscape-oriented; some parsers mis-handle rotated media boxes.

---
### Q29 · *OCR of noisy scanned page* · **adversarial**
**Q:** According to the 1998 memorandum, what was the preliminary depth estimate and which vessel took the sounding?

**Expected:** 5,340 metres (uncorrected), from RV Thalassa Verne, 14 March 1998, PI Dr. Elias Grunwald

**Where:** Scanned memo page (after Sec 8)

*Note:* Full-page degraded scan: rotation ~1.3 deg, noise, blur, coffee ring, scan lines.

---
### Q30 · *temporal reasoning across sources* · **adversarial**
**Q:** Why does the 1998 depth figure differ from the current certified station depth?

**Expected:** Trap T5 (temporal): the 1998 value (5,340 m) was a single-beam, sound-velocity-uncorrected estimate; the certified depth of 5,210 m is multibeam-corrected (2023). It is a historical revision, not an inconsistency.

**Where:** Scanned memo + Table B-1 + Sec 8 closing note

---
### Q31 · *form-layout field extraction* · **medium**
**Q:** On requisition REQ-7741, what are the unit cost, total, and priority?

**Expected:** Unit cost EUR 18,400; total EUR 36,800; priority 'Urgent' (checked box)

**Where:** Sec 9 form page

*Note:* Checkbox state must be read from ballot glyphs.

---
### Q32 · *JSON/code retrieval* · **easy**
**Q:** What chunk size does the mtrc-ingest pipeline use?

**Expected:** 512 kB (chunk_size_kb: 512)

**Where:** Sec 10 JSON config block

---
### Q33 · *table lookup* · **easy**
**Q:** How long is raw acoustic (hydrophone) data retained?

**Expected:** 25 years

**Where:** Table 10-1

---
### Q34 · *table lookup (dates)* · **easy**
**Q:** When does Benthic Disturbance Permit BD-2025-114 expire?

**Expected:** 30 June 2027

**Where:** Table 11-1

---
### Q35 · *two-column layout retrieval* · **medium**
**Q:** What triggers the ANDON PROTOCOL and what does it authorise?

**Expected:** Two independent hull sensors alarming within 90 seconds; authorises immediate crew ascent without surface concurrence

**Where:** Appendix A glossary (two-column layout)

*Note:* Column-order errors scramble glossary entries.

---
### Q36 · *cross-reference hop* · **hard**
**Q:** What is the CTD-9 conductivity cell constant (kappa) and its calibration date?

**Expected:** 0.9821 +/- 0.0004; calibrated 2025-01-19

**Where:** Sec 4.3 pointer -> Appendix B Table B-1

*Note:* Question is seeded in Sec 4.3 but the value lives only in Table B-1.

---
### Q37 · *long appendix table lookup* · **medium**
**Q:** In which storage jar is holotype accession MTRC-B-0442 held, and what taxon is it?

**Expected:** Jar 17; Hirondellea grunwaldi (holotype-flagged)

**Where:** Table C-1, Appendix C

*Note:* Holotype indicated by a filled-circle glyph column.

---
### Q38 · *image-embedded text (diagram)* · **hard**
**Q:** According to the station layout diagram, which module contains Laboratories 1-3?

**Expected:** Module E

**Where:** Figure 1-1 (diagram image)

*Note:* Stated only inside the diagram raster.

---
### Q39 · *image-embedded text (org chart)* · **hard**
**Q:** Who is the consortium's Chief Engineer?

**Expected:** Priya Raghunathan

**Where:** Figure 2-1 (org chart image)

*Note:* All leadership names exist only in the org-chart image.

---
### Q40 · *contradiction trap + numeric collision* · **adversarial**
**Q:** What is the station's depth?

**Expected:** CONFLICT (Trap T1): Exec Summary says 5,120 m; Sec 1, Table 1-1 and Table B-1 say 5,210 m (certified, multibeam-corrected). Ideal answer prefers 5,210 m and flags the exec-summary discrepancy. Bonus distractor: '5,120' also appears as EUR 5,120k in Table 6-1.

**Where:** Exec Summary vs Sec 1/Tables

---
### Q41 · *hyperlink/cover extraction* · **medium**
**Q:** What URL is given for the report's data portal?

**Expected:** https://data.mtrc-consortium.example/ar2025

**Where:** Cover page (hyperlink)

---
### Q42 · *image/text corroboration* · **medium**
**Q:** Which figure must NOT be used to answer 'how many berths does Module B provide' from text alone, and what is the value?

**Expected:** 22 berths - stated on the station diagram (Figure 1-1); the Exec Summary independently mentions 'up to twenty-two personnel', a partial textual echo

**Where:** Figure 1-1 + Exec Summary

*Note:* Tests whether the pipeline distinguishes image-sourced vs text-sourced support.

---
