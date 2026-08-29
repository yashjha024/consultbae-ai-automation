# Data quality report

This report is from the supplied files, not a generic checklist. The pipeline retains every physical row in `source_records`; rows that cannot be trusted are marked invalid and not matched.

| Source | Field / issue | Evidence found | Handling |
|---|---|---|---|
| Naukri (42 rows) | Exact duplicate row | `Rohit Verma` appears twice with the same email, phone, city, experience, CTC, date, and skills (rows 25 and 31). | Both rows remain as provenance records and resolve to one person through the normalized email/phone. |
| Naukri | Duplicate names with identifiers | `Nikhil Chopra` appears twice: same normalized phone `+919000000103`, but two emails (`alt...` and non-`alt...`). | The phone is the safe link; both source records attach to one person, and both raw emails remain in field provenance. |
| Naukri | Abbreviated/inconsistent names | `R. Verma` and `Rohit Verma` share `rohit.verma13@mailtest.example.org` and `+919000000294`. | They merge only because of strong identifiers - never because the names are similar. |
| Naukri | Phone formatting | Local digits, leading-zero local digits, and `+91` forms occur, e.g. `9000000113`, `09000000287`, `+919000000254`. | Valid Indian values normalize to `+91` plus ten digits; raw values remain preserved. |
| Naukri | City spelling/case/whitespace | 16 raw city values include `GURGAON`, `gurugram `, `Bangalore`, `NOIDA`, and `new delhi`. | Trim, case-fold, then map Gurgaon/Gurugram, Bangalore/Bengaluru, and Delhi/New Delhi/Delhi NCR to a controlled city. |
| Naukri | CTC has mixed, undocumented units | Values include `4.2`, `8.3`, `11.9` alongside `417964`, `775670`, and `1195422`; 20 values are below 20 while 22 are six/seven-digit amounts. | Stored raw only. No monetary conversion is invented because the unit is not specified. |
| Naukri | Dates use incompatible formats | ISO (`2026-08-08`), DD-MM (`24-07-2026`), US-style slash (`07/13/2026`), and textual (`7 Jul 2026`) values occur. Slash dates such as `07/03/2026` are inherently ambiguous. | Raw date is retained; this version intentionally does not create a potentially wrong canonical date. |
| Gig workers (32 rows) | Blank separator row | Physical row 12 is `,,,,,`. It creates a missing value in every column. | Saved as invalid with an explicit ingestion error; no person is created. |
| Gig workers | Column-shifted row | Row 19 starts with `"react, javascript, mysql"` in `email_id`, while the email is in `worker_name`; every field is shifted. | Saved as invalid rather than attempting a risky repair. |
| Gig workers | Email case inconsistency | Examples include `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`, `VARUN.SAXENA21@EXAMPLE.IN`, and lower-case equivalents. | Basic validated emails case-fold before matching; raw case is retained. |
| Gig workers | Status casing/category drift | `Active`, `active`, `ACTIVE`, `Inactive`, and `paused` occur (six raw values after excluding the blank row). | Case-folded to `active`, `inactive`, or `paused`; no semantic collapse is made between inactive and paused. |
| Gig workers | Mixed rate units | `1415/hr`, `403/hr`, `15k/month`, and `73k/month` are all present. | Stored raw; hourly and monthly rates are not compared or converted without assumptions about hours/currency. |
| Gig workers | Name collision | `Deepak Nair` occurs twice with different emails (`...44@example.com`, `...57@example.in`) and different locations. | Kept as two people: name equality alone is never a match. |
| All three | Location formatting | Case/whitespace and aliases recur, especially `Noida `, `PUNE`, `bangalore`, and `gurugram `. | One deterministic city normalizer is used across sources. |
| CBNexus (31 rows) | Repeated CSV header in data | A second `Name,Phone Number,City,Verified,Projects Completed` header occurs at physical row 16. | Saved as invalid with an explicit error and excluded from matching. |
| CBNexus | Phone formatting | Local, `91`-prefixed, and punctuated `+91-...` values occur. | Same Indian-phone normalizer as Naukri. |
| CBNexus | Verification categorical drift | `Y`, `yes`, `Yes`, `N`, and `No` occur. | Normalized to `verified` or `not_verified`, preserving raw evidence. |
| CBNexus | Same name, different people | `Arjun Mehta` appears with `+919000000131` and `+919000000272`. | They remain separate unless another strong identifier links them. |

## Resolution results after ingestion

There are 105 physical input rows. Three are invalid (the blank gig row, the shifted gig row, and the repeated CBNexus header), leaving 102 matchable source records. The current run creates 60 canonical people and 42 strong-identifier links; 25 people have records from more than one source. These values are asserted by the automated tests where appropriate.
