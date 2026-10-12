# Institutional data scale research for a university platform

**Research date:** 2026-10-09  
**Purpose:** Give the system-design specification sourced population anchors and transparent workload assumptions for a student and institutional data platform sized around Acıbadem University.  
**Evidence standard:** First-party institutional reports and official Turkish higher-education sources. Public enrollment is evidence; row counts and storage projections below are engineering estimates, not published Acıbadem database measurements.

## Executive findings

- Acıbadem Mehmet Ali Aydınlar University’s latest public Institutional Internal Evaluation Report available in this research reports **6,475 students** (3,644 undergraduate, 2,372 associate degree, 459 graduate), **585 academic staff**, and **300 administrative staff**. It reports these as the university’s 2025–26 education year figures. This is the best local sizing anchor; it implies 7,360 current student and employee identities before adding alumni, applicants, guests, or duplicate/inactive records. [Acıbadem 2025 Institutional Internal Evaluation Report, pp. 2–3](https://www.acibadem.edu.tr/sites/default/files/document/2025-kidr-raporu.pdf)
- Acıbadem explicitly describes its Student Information System (OBS) as the place where student academic data is processed and retained during education. Its Education Management System (EYS) is integrated with OBS and supports content, synchronous/asynchronous education, assessments, reporting, homework, forums and exams. Public materials disclose no event volume, peak concurrency, or database size. [Acıbadem Information Technologies](https://www.acibadem.edu.tr/en/student/life-at-acu/information-technologies)
- Türkiye reported **7,330,932 enrolled students in 2024** across its higher education institutions. A 2022–23 YÖK statistics release gives **6,950,142 students across 208 institutions**, including 735,433 at foundation universities. These are useful national context but include institutions and modalities with radically different sizes; they are not a sizing multiplier for Acıbadem. [YÖK 2024 student total](https://www.yok.gov.tr/en/Sayfalar/news/2025/women-s-access-to-higher-education-and-their-academic-presence-on-rise.aspx); [YÖK 2022–23 statistics](https://www.yok.gov.tr/en/Sayfalar/news/2023/new-statistics-in-higher-education.aspx)
- The public sources support a **small-to-mid-sized university core SIS** rather than a claim about exact bytes. For a first release, model 6.5k active students, 0.9k staff, and approximately 10k–20k people including alumni/applicants/guests; maintain a separate growth scenario at 25k active learners. Keep SIS row storage separate from files/media and high-volume audit/LMS telemetry.

## Acıbadem population and system evidence

| Metric | Public value | What it means for sizing | Source |
|---|---:|---|---|
| Students (2025–26) | 6,475 | Base active student dimension | [2025 KİDR](https://www.acibadem.edu.tr/sites/default/files/document/2025-kidr-raporu.pdf), pp. 2–3 |
| Undergraduate students | 3,644 | 56.3% of reported total | Same report |
| Associate degree students | 2,372 | 36.6% | Same report |
| Graduate students | 459 | 7.1% | Same report |
| Academic staff | 585 | Staff accounts, teaching assignments, research profiles | Same report |
| Administrative staff | 300 | Staff identities and role assignments | Same report |
| Campus area | ~90,000 m² | Context only; not a database volume predictor | Same report |
| Student-facing systems | OBS, EYS, BademNET, AVESIS, ASOS, UZEM, online payment, webmail | Integration, identity, sync, and operational log sources; count does not reveal traffic or retained bytes | [Acıbadem IT page](https://www.acibadem.edu.tr/en/student/life-at-acu/information-technologies) |

Acıbadem says OBS retains student academic data through their education; EYS uses OBS credentials/integration and supports course content, tests, assignments, forums and exams. Its UZEM FAQ also documents a scheduled background process that updates learning activity completion reports at intervals because continuous execution could slow the service; completion status can therefore lag (up to one week in the stated FAQ). This is direct evidence to treat LMS activity reporting as asynchronous and to avoid putting every LMS progress event on a synchronous SIS transaction path. [IT page](https://www.acibadem.edu.tr/en/student/life-at-acu/information-technologies); [UZEM FAQ](https://www.acibadem.edu.tr/en/application-and-research-centers/uzem/faq)

Acıbadem’s 2024 report listed 6,324 students (3,489 undergraduate, 2,368 associate degree, 467 graduate), while the 2025 report lists 6,475. This is a 151-student increase (2.4%) year over year. Treat this as a single observed annual change, not a forecast. [2024 report](https://www.acibadem.edu.tr/sites/default/files/document/2024_K%C4%B0DR_raporu-28.03.2025_0.pdf), pp. 1–2; [2025 report](https://www.acibadem.edu.tr/sites/default/files/document/2025-kidr-raporu.pdf), pp. 2–3.

## Comparison anchors

| Institution / population reference | Official value | Appropriate use | Source |
|---|---:|---|---|
| Acıbadem University, 2025–26 | 6,475 students; 585 academic and 300 administrative staff | Local design anchor | [2025 KİDR](https://www.acibadem.edu.tr/sites/default/files/document/2025-kidr-raporu.pdf), pp. 2–3 |
| Sabancı University, 2024–25 spring term | 4,114 undergraduate + 869 graduate = 4,983 students; 461 faculty; 433 administrative staff | Similar-sized private university comparison | [Facts and Figures](https://iro.sabanciuniv.edu/en/facts-and-figures); statistics as of 2024–25 Spring Term |
| Koç University, 2024–25 | 9,156 students; 627 teaching staff | Larger private university comparison | [Koç University 2024–25 report, p. 4](https://cdn.ku.edu.tr/cdn/files/KU/ku24-25/files/basic-html/page4.html) |
| Bilkent University, 2024–25 | 10,657 full-time students; 658 full-time academicians; 656 full-time administrative staff | Larger private university comparison | [Bilkent population reporting](https://sustainable.bilkent.edu.tr/energyandclimatechange2-2/), 2024–25 academic year |
| Türkiye, all higher education, 2024 | 7,330,932 students | National scale/context; broad upper benchmark | [YÖK](https://www.yok.gov.tr/en/Sayfalar/news/2025/women-s-access-to-higher-education-and-their-academic-presence-on-rise.aspx) |
| Türkiye, 2022–23 | 6,950,142 students; 208 institutions | Institutional ecosystem context | [YÖK](https://www.yok.gov.tr/en/Sayfalar/news/2023/new-statistics-in-higher-education.aspx) |
| Foundation universities, 2022–23 | 735,433 students | Sector context for Acıbadem’s foundation-university status | [YÖK](https://www.yok.gov.tr/en/Sayfalar/news/2023/new-statistics-in-higher-education.aspx) |
| 18 universities in earthquake-affected region, 2024 | 402,121 students; 16,200 academic staff | Cross-check against a multi-institution cohort | [YÖK](https://www.yok.gov.tr/Sayfalar/Haberler/2025/depremden-etkilenen-universiteler.aspx) |

The named peers show a useful private-university planning band of roughly 5,000–10,700 enrolled/full-time students around Acıbadem’s reported 6,475. Reporting periods and population definitions are not perfectly aligned (Sabancı is explicitly spring-term; Bilkent reports full-time population; Koç’s public page gives headline student count), so compare them as sizing anchors rather than a precise ranking. These figures show why “university” cannot be represented by one universal population assumption. Publicly available official sources reviewed here do not provide comparable live SIS row counts, LMS event rates, or table byte sizes for these institutions.

## Capacity model: sourced facts vs. engineering assumptions

The model below translates the 6,475-student anchor into plausible relational row counts. The formulas are deliberately explicit so they can be replaced with measured institutional data. “Course registrations” means student-course attempts/semester enrollments; it is not a claim about Acıbadem’s actual courses per term. Values are order-of-magnitude capacity planning figures.

### Row-count assumptions

| Entity / fact | Formula | Planning count | Classification |
|---|---|---:|---|
| Current students | Reported total | 6,475 | Sourced fact |
| Student + employee identities | 6,475 + 585 + 300 | 7,360 | Derived from sourced facts; excludes alumni/applicants |
| Courses offered per academic year | 6,475 students × 5 distinct enrollments/term × 2 terms ÷ 25 students/section | ~2,590 course sections/year | Illustrative assumption; section sizes vary widely, clinical cohorts can be small |
| Course enrollment rows/year | 6,475 × 5 enrollments/term × 2 terms | 64,750 | Illustrative assumption |
| Course enrollment history, 6 years | 64,750 × 6 | 388,500 | Illustrative assumption; includes attempts and repeats if modeled per attempt |
| Grade rows, 6 years | 388,500 × 4 graded components/course | 1,554,000 | Illustrative assumption; assessments per class are highly variable |
| Attendance events/year | 6,475 × 5 courses/term × 2 terms × 14 weeks × 2 meetings/week | 1,813,000 | Illustrative assumption; not all courses take attendance twice weekly |
| Attendance history, 6 years | 1,813,000 × 6 | 10,878,000 | Illustrative assumption |
| Learning activity events/year | 6,475 × 10 interactions/day × 180 teaching days | 11,655,000 | Stress estimate only; “interaction” definition and actual telemetry unknown |
| Learning activity history, 6 years | 11,655,000 × 6 | 69,930,000 | Stress estimate; should live in partitioned event/analytics storage with retention rules |

Course, grade, attendance, and LMS values are scenario calculations, not sourced system telemetry. They should be calibrated by exporting aggregate counts from the production SIS/LMS or running a representative pilot. Clinical rotations, admissions applications, payment attempts, audit events, and attachments are omitted because sources reviewed do not publish their counts.

### Approximate database size—not an observed vendor/system measurement

For preliminary planning, an average narrow normalized SIS row (foreign keys, timestamps, small codes, limited text) might occupy around **0.2–1.0 KB before index and replication overhead**. This is a generic engineering assumption; actual physical size depends on DBMS, row format, index design, fill factor, compression, text columns and retention. Binary uploads must be stored separately in object/file storage.

| Data set | Approximate raw logical size from assumed row widths |
|---|---:|
| 7,360 identity rows × 1–3 KB/person | ~7–22 MB |
| 388,500 course enrollment rows × 0.2–0.6 KB | ~78–233 MB |
| 1,554,000 grade rows × 0.2–0.6 KB | ~311–932 MB |
| 10,878,000 attendance rows × 0.1–0.3 KB | ~1.1–3.3 GB |
| 69,930,000 learning events × 0.1–0.3 KB | ~7.0–21 GB |
| **Subtotal** | **~8.5–25.5 GB logical** |

The wide range is intentional. It excludes admissions, billing, course catalog/history, files/video, indexes, WAL/binlogs, backups, replicas, and derived reporting datasets. Applying a 2–3× operational overhead to the subtotal (indexes, storage-engine overhead, and near-term growth) gives roughly **17–77 GB primary database capacity**, before backup and media storage. This multiplier is an engineering reserve, not a universal factor or measured Acıbadem value. A reasonable initial deployment can provision well below this by separating LMS event logs and attachments from transactional SIS tables, then monitor measured bytes per row and growth monthly.

## Sizing / load-test targets to adopt provisionally

These are proposed targets for validation, not public benchmarks:

- **Population:** 6,500 active-student baseline; 10,000 active-student design point; 25,000 learner stress scenario. Keep five years of academic history online and establish explicit retention for audit and LMS events.
- **Peak synchronous users:** test 10%, 25%, and 40% of active students concurrently (650, 1,625, 2,600 at baseline; 2,500, 6,250, 10,000 at the 25k scenario). Registration, grades release, and exam windows should be separate workload profiles.
- **Transaction load:** measure registration reads/writes, timetable queries, grading submissions, and notification fan-out under realistic session mixes. Do not infer requests per second from enrollment alone.
- **Storage:** measure actual row sizes and index footprint from a seeded representative dataset; track SIS data, LMS events, files, and backups independently. Use growth alarms at 70/80/90% disk and test restore times.
- **Growth:** update the population anchor annually from KİDR/YÖK and update event multipliers from actual vendor exports. A measured monthly/semester growth series is needed for a credible 3–5 year forecast.

## Data-quality and evidence gaps

Public institution publications give population and system descriptions, but not production database sizes, concurrent session counts, TPS, retention schedules, or table-level rows/columns. The report therefore cannot responsibly state Acıbadem’s “actual raw size per table.” Obtain (1) anonymized count-only exports per SIS/LMS entity, (2) DB statistics for average row/index sizes, (3) peak 5-minute web/API concurrency and request rates around registration/exam periods, (4) file object totals and byte distributions, (5) retention and deletion rules, and (6) integration synchronization frequency/error backlog. Avoid exporting student personal data for this sizing exercise.

## References

1. Acıbadem Mehmet Ali Aydınlar University, [2025 Institutional Internal Evaluation Report (2025 KİDR)](https://www.acibadem.edu.tr/sites/default/files/document/2025-kidr-raporu.pdf).
2. Acıbadem Mehmet Ali Aydınlar University, [2024 Institutional Internal Evaluation Report (2024 KİDR)](https://www.acibadem.edu.tr/sites/default/files/document/2024_K%C4%B0DR_raporu-28.03.2025_0.pdf).
3. Acıbadem Mehmet Ali Aydınlar University, [Information Technologies and institutional system descriptions](https://www.acibadem.edu.tr/en/student/life-at-acu/information-technologies).
4. Acıbadem Mehmet Ali Aydınlar University, [UZEM / distance education FAQ](https://www.acibadem.edu.tr/en/application-and-research-centers/uzem/faq).
5. Council of Higher Education of Türkiye (YÖK), [2024 student population](https://www.yok.gov.tr/en/Sayfalar/news/2025/women-s-access-to-higher-education-and-their-academic-presence-on-rise.aspx).
6. YÖK, [2022–23 higher education statistics](https://www.yok.gov.tr/en/Sayfalar/news/2023/new-statistics-in-higher-education.aspx).
7. YÖK, [2024 figures for 18 earthquake-affected universities](https://www.yok.gov.tr/Sayfalar/Haberler/2025/depremden-etkilenen-universiteler.aspx).
8. Sabancı University, [Facts and Figures](https://iro.sabanciuniv.edu/en/facts-and-figures), Spring 2024–25.
9. Koç University, [2024–25 report, headline facts](https://cdn.ku.edu.tr/cdn/files/KU/ku24-25/files/basic-html/page4.html).
10. Bilkent University, [population and activity figures](https://sustainable.bilkent.edu.tr/energyandclimatechange2-2/), 2024–25.
