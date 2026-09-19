# Statutory Engine Verification & Remediation Status (Round 1)

**Date:** September 2026  
**Auditor / Engine Maintainer:** NETRA Engineering Team  
**Statutory Framework:** Legal Metrology Act, 2009 & Legal Metrology (Packaged Commodities) Rules, 2011 (as amended through G.S.R. 629(E))  
**Target Package:** `netra_core` (`core/netra_core/`)

## Verification & Remediation Ledger

| Issue ID | Description | Phase 0 Empirical Status | Remediation Status (Round 1) |
|---|---|---|---|
| **Issue 1** | Rule 13 prohibited units false-positive on address ("GMS Industrial Area") | Verified Present (Confirmed) | **FIXED & TESTED** (Scoped to `net_qty`, `usp`) |
| **Issue 2** | Pipeline crash (`ValueError`) on Area/Sheet Net Quantities (`m2`, `cm2`) in USP | Verified Present (Confirmed) | **FIXED & TESTED** (Area returns `NA` per Rule 6(11) + defensive `try..except`) |
| **Issue 3** | Missing "PKD" / "PKD." Date Anchors Rejecting Standard Indian Packs | Verified Present (Confirmed) | **FIXED & TESTED** (Added `r"\bpkd\.?\b"` anchor) |
| **Issue 4** | Strict 4-Digit Year Requirement Rejecting 2-Digit Date Stamps | Legal-Design Call (Preserved) | Deferred (Pending field evidence & policy decision) |
| **Issue 5** | Missing "Net Vol." / "Net Volume" Anchor Rejecting Liquid Products | Verified Present (Confirmed) | **FIXED & TESTED** (Added `vol(?:ume)?` pattern) |
| **Issue 6** | Decimal USP Stealing MRP Value in `parse_money_lenient` | Verified Present (Confirmed) | **FIXED & TESTED** (Bounded search before USP/RSP anchors, preserved glyph guard) |
| **Issue 7** | Strict Tax Phrasing ("incl. GST" vs "incl. of all taxes") | Legal-Design Call (Preserved) | Deferred (Pending field evidence & policy decision) |
| **Issue 8** | Spatial Anchor Overwrite on Multi-Entity Addresses | Backlog | Backlog Register |
| **Issue 9** | Imported Products Failing Address Check When Naming Importer/Marketer | Backlog | Backlog Register |
| **Issue 10** | Evidence Bounding Box Disconnect When OCR Fails on Present Fields | Deferred | Deferred (Python + Dart cross-stack design) |
| **Issue 11** | Font Height Overestimation from Full Text Bounding Box | Backlog | Backlog Register |
| **Issue 12** | Generic Product Name Conflation with Brand Trademarks | Backlog | Backlog Register |

## Test & Gate Verification Results Summary
- **Pre-Gate Baseline:** 394 passed / 1 skipped (395 collected). All 5 tests beyond the 389 ledger explained via git history (commits `0e04141` and `d72dfc9`).
- **Remediation Suite:** `core/tests/test_engine_audit_fixes.py` (7 tests covering Issues 1, 2, 3, 5, 6 + OCR glyph guard). 7 passed in 2.37s.
- **Full Engine Regression Suite:** **401 passed / 1 skipped in 84.59s** (402 collected). Zero regressions, exact match for `394 baseline + 7 new`.
- **Wheel Build & Parity:** `netra_core-0.1.0-py3-none-any.whl` rebuilt, hash verified, verified parity across all modified modules (`usp.py`, `parsers.py`, `s5_field_extract.py`, `s6_metrology.py`), `s2_roi_merge.py`, `schema.py` (`roi_boxes`), and `vision_config.json` (`yolo`).

---

# NETRA Statutory Engine: Legal Metrology Rules, Logic & Vulnerability Audit

**Document Version:** 1.0.0  
**Target System:** `netra_core` Statutory Metrology Pipeline (`core/netra_core/`)  
**Statutory Framework:** Legal Metrology Act, 2009 & Legal Metrology (Packaged Commodities) Rules, 2011 (as amended through G.S.R. 629(E))  
**Audit Scope:** Rules, Math Formats, Parsers, Regular Expressions, Pass/Fail Thresholds, Spatial Field Extraction, and Latent Systemic Issues.

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Complete Statutory Rulebook & Decision Logic](#2-complete-statutory-rulebook--decision-logic)
   - [Rule 26: Statutory Exemptions](#rule-26-statutory-exemptions-rulesexemptionspy)
   - [Rule 13: Metric Unit Syntax & Prohibited Symbols](#rule-13-metric-unit-syntax--prohibited-symbols-rulessi_unitspy)
   - [Rule 6(1)(c): Net Quantity Declaration](#rule-61c-net-quantity-declaration-rulesdeclarationspy-rulesparserspy)
   - [Rule 6(1)(e): Maximum Retail Price (MRP)](#rule-61e-maximum-retail-price-mrp-rulesdeclarationspy-rulesparserspy)
   - [Rule 6(11): Unit Sale Price (USP) Mathematical Verification](#rule-611-unit-sale-price-usp-mathematical-verification-rulesusppy)
   - [Rule 6(1)(d): Month and Year of Manufacture / Packing](#rule-61d-month-and-year-of-manufacture--packing-rulesdeclarationspy-rulesparserspy)
   - [Rule 6(1)(a): Manufacturer, Packer, or Importer Identification](#rule-61a-manufacturer-packer-or-importer-identification-rulesdeclarationspy)
   - [Rule 6(1)(aa): Country of Origin (Imported Commodities)](#rule-61aa-country-of-origin-imported-commodities-rulesdeclarationspy)
   - [Rule 6(1)(n): Consumer Care & Grievance Mechanism](#rule-61n-consumer-care--grievance-mechanism-rulesdeclarationspy)
   - [Rule 6(1)(b): Common / Generic Commodity Name](#rule-61b-common--generic-commodity-name-rulesdeclarationspy)
   - [Rule 7: Table-I Font Heights & Principal Display Area (PDA)](#rule-7-table-i-font-heights--principal-display-area-pda-rulestable1_fontspy)
   - [Rule 7(3): Character Width-to-Height Ratio](#rule-73-character-width-to-height-ratio-rulestable1_fontspy)
3. [Deep-Dive Audit: 12 Latent Issues, Bugs & Edge Cases](#3-deep-dive-audit-12-latent-issues-bugs--edge-cases)
   - [Issue 1: False Rule 13 Violations from Company Names & Postal Addresses](#issue-1-false-rule-13-violations-from-company-names--postal-addresses)
   - [Issue 2: Pipeline Crash (`ValueError`) on Area/Sheet Net Quantities in USP Engine](#issue-2-pipeline-crash-valueerror-on-areasheet-net-quantities-in-usp-engine)
   - [Issue 3: Missing "PKD" / "PKD." Date Anchors Rejecting Standard Indian Packs](#issue-3-missing-pkd--pkd-date-anchors-rejecting-standard-indian-packs)
   - [Issue 4: Strict 4-Digit Year Requirement Rejecting 2-Digit Date Stamps](#issue-4-strict-4-digit-year-requirement-rejecting-2-digit-date-stamps)
   - [Issue 5: Missing "Net Vol." / "Net Volume" Anchor Rejecting Liquid Products](#issue-5-missing-net-vol--net-volume-anchor-rejecting-liquid-products)
   - [Issue 6: Decimal USP Stealing MRP Value in `parse_money_lenient`](#issue-6-decimal-usp-stealing-mrp-value-in-parse_money_lenient)
   - [Issue 7: Overly Strict Tax Phrasing Rejecting Common Formulations](#issue-7-overly-strict-tax-phrasing-rejecting-common-formulations)
   - [Issue 8: Spatial Anchor Overwrite on Multi-Entity Addresses](#issue-8-spatial-anchor-overwrite-on-multi-entity-addresses)
   - [Issue 9: Imported Products Failing Address Check When Naming Importer/Marketer](#issue-9-imported-products-failing-address-check-when-naming-importermarketer)
   - [Issue 10: Evidence Bounding Box Disconnect When OCR Fails on Present Fields](#issue-10-evidence-bounding-box-disconnect-when-ocr-fails-on-present-fields)
   - [Issue 11: Font Height Overestimation from Full Text Bounding Box](#issue-11-font-height-overestimation-from-full-text-bounding-box)
   - [Issue 12: Generic Product Name Conflation with Brand Trademarks](#issue-12-generic-product-name-conflation-with-brand-trademarks)
4. [Evidence Linking & UI Display Verification](#4-evidence-linking--ui-display-verification)
5. [Summary Matrix of Checks & Failure Modes](#5-summary-matrix-of-checks--failure-modes)

---

## 1. Executive Summary

NETRA's metrology verification engine is a deterministic, high-speed legal rule system operating in `core/netra_core/rules/` and coordinated by pipeline stages `s5_field_extract.py` and `s6_metrology.py`. It converts raw text tokens and spatial bounding boxes into legally defensible verdicts under the Legal Metrology Act, 2009.

This audit details:
1. **The exact logic, statutory rules, regex expressions, mathematical formulas, and thresholds** used to calculate `PASS`, `FAIL`, and `NA`.
2. **Twelve (12) latent issues, bugs, and edge cases** that cause false violations, crashes, or missed declarations during field inspections.
3. As per instructions, **no code has been altered or patched**. All issues are documented with exact file paths, line references, root causes, and recommended future remediation steps.

---

## 2. Complete Statutory Rulebook & Decision Logic

```
                    +-----------------------------+
                    |  Stage 5: Extracted Fields  |
                    +-----------------------------+
                                   |
                                   v
                    +-----------------------------+
                    | Rule 26: Exemption Check    |
                    +-----------------------------+
                                   |
                 +-----------------+-----------------+
                 | Exempt                            | Not Exempt
                 v                                   v
          +--------------+             +-------------------------------+
          | Return NA    |             | Rule 13: Prohibited SI Units  |
          | Halts checks |             +-------------------------------+
          +--------------+                             |
                                       +---------------+---------------+
                                       |                               |
                                       v                               v
                        +-----------------------------+ +-----------------------------+
                        | Rule 6(1)(c): Net Qty       | | Rule 6(1)(e): MRP + Taxes   |
                        +-----------------------------+ +-----------------------------+
                                       |                               |
                                       +---------------+---------------+
                                                       |
                                                       v
                                        +-----------------------------+
                                        | Rule 6(11): USP Math Check  |
                                        +-----------------------------+
                                                       |
                        +------------------------------+------------------------------+
                        |                              |                              |
                        v                              v                              v
         +-----------------------------+ +-----------------------------+ +-----------------------------+
         | Rule 6(1)(d): Mfg Date      | | Rule 6(1)(a): Mfr / Address | | Rule 6(1)(aa): Origin       |
         +-----------------------------+ +-----------------------------+ +-----------------------------+
                        |                              |                              |
                        +------------------------------+------------------------------+
                                                       |
                        +------------------------------+------------------------------+
                        |                                                             |
                        v                                                             v
         +-----------------------------+                               +-----------------------------+
         | Rule 6(1)(n): Consumer Care |                               | Rule 6(1)(b): Product Name  |
         +-----------------------------+                               +-----------------------------+
                                                       |
                        +------------------------------+------------------------------+
                        |                                                             |
                        v                                                             v
         +-----------------------------+                               +-----------------------------+
         | Rule 7: Table-I Font Height |                               | Rule 7(3): Aspect Ratio     |
         +-----------------------------+                               +-----------------------------+
```

---

### Rule 26: Statutory Exemptions (`rules/exemptions.py`)

Rule 26 exempts specific packages from all requirements of the Legal Metrology (Packaged Commodities) Rules, 2011. NETRA evaluates this first. If a package is exempt, all remaining checks are bypassed and marked `NA`.

#### Statutory Logic & Thresholds
1. **Institutional / Industrial Supply (Rule 26(b)):**
   - Triggered by option flag `institutional=True`.
   - Package is supplied directly to an institutional/industrial consumer for their own use, not for retail resale.
   - *Verdict:* `NA` (Exempt).
2. **Fast Food / Restaurant Packing (Rule 26(c)):**
   - Triggered by option flag `fast_food=True`.
   - Package prepared and served hot/fresh by a hotel, restaurant, or canteen.
   - *Verdict:* `NA` (Exempt).
3. **Small Package Threshold (Rule 26(a)):**
   - Net Quantity $\le 10\text{ g}$ OR $\le 10\text{ mL}$.
   - **Exclusion (Second proviso to Rule 26(a)):** Packages containing **tobacco**, **bidi**, **pan masala**, or **panmasala** are **expressly excluded** from the small-package exemption and must carry all Rule 6 declarations regardless of how small they are.
   - *Verdict:* `NA` (Exempt) if $\le 10\text{ g} / 10\text{ mL}$ and commodity is not tobacco-related; `FAIL/Active` if tobacco.
4. **Bulk Packages (Rule 26(a)):**
   - Net Quantity $> 25\text{ kg}$ OR $> 25\text{ L}$.
   - **Cement & Fertilizer Carve-Out:** For cement and fertilizers, the bulk exemption threshold is raised from $25\text{ kg}$ to $> 50\text{ kg}$. Cement/fertilizer bags up to $50\text{ kg}$ are **not** exempt.
   - *Verdict:* `NA` (Exempt) if net qty exceeds bulk threshold.

---

### Rule 13: Metric Unit Syntax & Prohibited Symbols (`rules/si_units.py`)

Rule 13 strictly forbids colloquial abbreviations, non-standard metric symbols, and imperial units on packaged goods.

#### Prohibited Regular Expression
```python
_PROHIBITED_RE = re.compile(
    r"(?<![a-z0-9])(gms|grm|kilo|kgs|ltr|cc|cu\.?\s*cm|pkts|doz)(?![a-z0-9])",
    re.IGNORECASE,
)
```

#### Permitted SI Unit Symbols
`mg`, `g`, `kg`, `ml`, `l`, `mm`, `cm`, `m`, `cm2`, `m2`, `n`, `u`, `piece`, `pair`, `set`.

#### Decision Logic
- **Iterates through all fields** (`net_qty`, `mrp`, `usp`, `mfg_address`, etc.) in `ctx.fields`.
- If any field matches `_PROHIBITED_RE`:
  - **Verdict:** `FAIL`.
  - **Message:** `"Prohibited unit syntax '<token>' in <Field> — statutory symbol '<suggestion>' required. Rule 13, Legal Metrology (Packaged Commodities) Rules, 2011"`
  - Suggestions mapped: `gms -> g`, `grm -> g`, `kilo -> kg`, `kgs -> kg`, `ltr -> L`, `cc -> mL`, `cu.cm -> mL`, `pkts -> piece`, `doz -> piece`.
- If no prohibited tokens found:
  - **Verdict:** `PASS`.
  - **Message:** `"No prohibited unit symbols (gms, grm, kilo, kgs, ltr, cc, pkts, doz)."`

---

### Rule 6(1)(c): Net Quantity Declaration (`rules/declarations.py`, `rules/parsers.py`)

Requires clear declaration of the net quantity in terms of standard units of mass, volume, length, area, or number.

#### Anchor Detection Regex (`s5_field_extract.py:57`)
```python
_ANCHORS[FIELD_NET_QTY] = (
    r"\bnet\s*(?:quantity|qty|qnty|wt|weight|contents?)\b",
    r"^(?:quantity|qty)\b",
)
```

#### Extraction & Validation Logic
1. Anchor search followed by value parsing using `parse_quantity()`:
   - Matches: Number followed by unit: `([0-9]+(?:[.,][0-9]+)?)\s*([a-z]+[0-9]?)`
2. Unit normalization and permitted check:
   - Permitted: `PERMITTED_UNITS`
   - Tolerated variants: `nos -> N`, `pcs/pc -> piece`, `units -> U`, `pairs -> pair`, `sets -> set`.
3. **Decision Criteria:**
   - If raw field is missing: **`FAIL`** (*"Net quantity declaration not detected."*)
   - If quantity cannot be decoded into number + unit: **`FAIL`** (*"Net quantity not decodable..."*)
   - If unit is not in `PERMITTED_UNITS` and not in `_TOLERATED_VARIANTS`: **`FAIL`** (*"Unit '<unit>' is not a standard SI symbol..."*)
   - If number and permitted/tolerated unit present: **`PASS`** (*"Net quantity <value> <unit> in standard unit."*)

---

### Rule 6(1)(e): Maximum Retail Price (MRP) (`rules/declarations.py`, `rules/parsers.py`)

Requires statutory declaration of MRP with mandatory inclusion of taxes.

#### Anchor & Component Regexes
```python
_MRP_KEYWORD_RE = re.compile(
    r"\b(?:m\.?r\.?p\.?|max(?:imum)?\.?\s*retail\s*price)\b", re.IGNORECASE)
_TAX_PHRASE_RE = re.compile(
    r"incl(?:usive)?\.?\s*(?:of\s+)?all\s+taxes?", re.IGNORECASE)
```

#### Decision Criteria
Rule 6(1)(e) requires three distinct elements:
1. **Keyword presence:** Must contain `MRP`, `M.R.P.`, or `Maximum Retail Price`.
2. **Rupee amount:** Parsed via `parse_money_lenient()`.
3. **Tax phrase:** Must match `_TAX_PHRASE_RE` (e.g., `incl. of all taxes`, `inclusive of all taxes`).
- If raw text is missing: **`FAIL`** (*"MRP declaration not detected."*)
- If any of the 3 elements is missing: **`FAIL`** (*"MRP non-compliant — missing <list of missing items>."*)
- If all 3 elements present: **`PASS`** (*"MRP Rs <amount> inclusive of all taxes."*)

---

### Rule 6(11): Unit Sale Price (USP) Mathematical Verification (`rules/usp.py`)

Mandates declaration of price per unit quantity (per gram, per kg, per mL, per litre, per metre, or per piece) to facilitate consumer price comparison.

#### Reference Unit Selection Rules
| Net Quantity Dimension | Net Quantity Range | Statutory Reference Unit | Mathematical Formula |
| :--- | :--- | :--- | :--- |
| **Mass** | $< 1\text{ kg}$ (e.g. $250\text{ g}$) | **per gram (`/ g`)** | $\text{MRP} / \text{qty in grams}$ |
| **Mass** | $> 1\text{ kg}$ (e.g. $5\text{ kg}$) | **per kilogram (`/ kg`)** | $\text{MRP} / \text{qty in kg}$ |
| **Volume** | $< 1\text{ L}$ (e.g. $500\text{ mL}$) | **per millilitre (`/ ml`)** | $\text{MRP} / \text{qty in mL}$ |
| **Volume** | $> 1\text{ L}$ (e.g. $2\text{ L}$) | **per litre (`/ L`)** | $\text{MRP} / \text{qty in L}$ |
| **Length** | $< 1\text{ m}$ (e.g. $50\text{ cm}$) | **per centimetre (`/ cm`)** | $\text{MRP} / \text{qty in cm}$ |
| **Length** | $> 1\text{ m}$ (e.g. $10\text{ m}$) | **per metre (`/ m`)** | $\text{MRP} / \text{qty in m}$ |
| **Number / Count** | Any count $> 1$ (e.g. $10\text{ N}$) | **per piece (`/ piece` or `/ N`)** | $\text{MRP} / \text{count}$ |

#### Exemptions (Second Proviso to Rule 6(11))
A separate USP declaration is **exempt** if:
- Net quantity is **exactly 1 unit / piece** (`count == 1`).
- Net quantity is **exactly $1\text{ kg}$**, **$1\text{ L}$**, or **$1\text{ m}$**. In these cases, the MRP is already the Unit Sale Price.

#### Decision Logic & Tolerances
- **Math Tolerance:** $\text{TOLERANCE} = \text{Rs } 0.01$ (1 paisa).
- If MRP or Net Quantity is missing: **`NA`** (*"USP not evaluable — MRP or net quantity missing."*).
- If package qualifies for 1-unit exemption: **`PASS`** (*"Second proviso to Rule 6(11): net quantity is exactly one... RSP itself is the USP."*).
- If USP is undeclared: **`FAIL`** (*"USP not declared. Statutory requirement: Rs <expected> per <unit>"*).
- If declared unit does not match reference unit: **`FAIL`** (*"wrong reference unit — declared '<du>', statutory '<required>'"*).
- If $|\text{declared\_value} - \text{calculated\_value}| > 0.01$: **`FAIL`** (*"USP math error — declared Rs <declared> vs calculated Rs <expected>"*).
- If unit and math match within tolerance: **`PASS`** (*"USP declared correctly: Rs <declared> per <unit>."*).

---

### Rule 6(1)(d): Month and Year of Manufacture / Packing (`rules/declarations.py`, `rules/parsers.py`)

Requires clear declaration of the date on which the commodity was manufactured, packed, or imported.

#### Statutory Formats
```python
_DMY_RE  = r"(?<![0-9])([0-9]{1,2})\s*[/\-.]\s*([0-9]{1,2})\s*[/\-.]\s*([0-9]{4})(?![0-9])"
_MY_RE   = r"(?<![0-9])([0-9]{1,2})\s*[/\-.]\s*([0-9]{4})(?![0-9])"
_MONY_RE = r"([a-z]{3,9})\s*[\-,. ]{0,3}\s*([0-9]{4})(?![0-9])"
```
Valid year range: $1970 \le \text{Year} \le 2100$.

#### Decision Criteria
- If raw text is missing: **`FAIL`** (*"Date of manufacture / packing not detected."*)
- If text cannot be parsed by any of `_DMY_RE`, `_MY_RE`, or `_MONY_RE`: **`FAIL`** (*"Date '<text>' is not in a statutory form (MM/YYYY, Month YYYY, or DD/MM/YYYY) — Rule 6(1)(d)."*)
- If successfully parsed: **`PASS`** (*"Date of manufacture <MM/YYYY>."*)

---

### Rule 6(1)(a): Manufacturer, Packer, or Importer Identification (`rules/declarations.py`)

Requires the complete name and address of the manufacturer, or packer, or importer, including the postal PIN code.

#### Extraction Logic
1. PIN code extraction via `extract_pin()`:
   - Masks out phone numbers ($\ge 7$ digits).
   - Looks for `PIN / PINCODE / P.O. : [1-9][0-9]{2} [0-9]{3}` or bare 6-digit number `[1-9][0-9]{5}`.
2. Identifies entities:
   - Manufacturer: `_MFR_RE` (`mfg`, `mfd`, `manufactured by`, `made by`)
   - Packer: `_PACKER_RE` (`packed by`, `packers`)
   - Marketer: `_MARKETER_RE` (`marketed by`, `mktd by`)

#### Decision Criteria
- If address text is missing: **`FAIL`** (*"Manufacturer / packer / importer details not detected."*)
- If a third party (packer/marketer) is named, but no manufacturer is named:
  - **`FAIL`** (*"Packer / marketer is named without manufacturer details — Rule 6(1)(a) requires both when a third party packs the commodity."*)
- If PIN code is absent:
  - **`FAIL`** (*"Address present but no valid 6-digit PIN code found — Rule 6(1)(a) requires a complete postal address incl. PIN."*)
- If entity details and PIN are present:
  - **`PASS`** (*"Manufacturer/packer details with PIN <pin>."*)

---

### Rule 6(1)(aa): Country of Origin (Imported Commodities) (`rules/declarations.py`)

Every imported package must clearly state the country of origin.

#### Decision Logic
- Checks text against `COUNTRIES` (80 recognized countries) and `AMBIGUOUS_ORIGINS` (`prc`, `roc`, `eu`, `europe`, `asia`, `middle east`, `foreign`, `imported`).
- Scans for imported signals using `looks_imported()` (`import`, `importer`, `imported by`).
- **Decision Criteria:**
  - If a recognized country is found: **`PASS`** (*"Country of origin: <Country>."*)
  - If an ambiguous term (e.g. `PRC`, `EU`) is found: **`FAIL`** (*"Ambiguous origin '<term>' — Rule 6(1)(aa) requires an explicit country (e.g., 'Made in PRC' must read 'Made in China')."*)
  - If package looks imported but no origin is stated: **`FAIL`** (*"Country of origin missing — mandatory on imported packages (Rule 6(1)(aa))."*)
  - If package is domestic and origin is omitted: **`NA`** (*"Country of origin not found; mandatory for imported packages — flagged for manual review."*)

---

### Rule 6(1)(n): Consumer Care & Grievance Mechanism (`rules/declarations.py`)

Requires the name, address, telephone number, and email address of the person or office that can be contacted in case of a consumer complaint.

#### Required Elements
1. **Telephone helpline:** Checked by `_PHONE_RE`:
   - 1800 toll-free (e.g., `1800 123 4567`)
   - 1860 helplines
   - +91 landline with STD code (e.g., `+91-79-26856029`, `079-26856029`)
   - 10-digit mobile or +91 mobile (e.g., `9876543210`)
2. **Email address:** Checked by `_EMAIL_RE`:
   - Valid email syntax or `(at)` convention.
3. **Postal address:**
   - 6-digit PIN code in consumer care block, OR
   - Inherited manufacturer PIN `mfg_pin`, OR
   - Proviso phrase: `_AS_ABOVE_RE` (e.g., `"address as above"`, `"same as above"`, `"registered office address"`).

#### Decision Criteria
- If consumer care text is missing: **`FAIL`** (*"Consumer care details not detected."*)
- If any of {phone, email, postal address} is missing: **`FAIL`** (*"Consumer care incomplete — missing <missing items>."*)
- If all three elements present: **`PASS`** (*"Consumer care complete (tel <phone>, email <email>, <address>)."*)

---

### Rule 6(1)(b): Common / Generic Commodity Name (`rules/declarations.py`, `s5_field_extract.py`)

Requires the common or generic name of the commodity to be prominently displayed on the package.

#### Decision Logic
- In Stage 5, searches for the largest/tallest token cloud in the upper 65% of the principal display panel.
- Evaluated via `check_presence()`:
  - Text must have length $\ge 3$ and contain at least one alphabetic character.
- **Decision Criteria:**
  - If detected: **`PASS`** (*"Common / generic name present — semantic adequacy needs manual review."*)
  - If missing: **`FAIL`** (*"Common / generic name not found on the package."*)

---

### Rule 7: Table-I Font Heights & Principal Display Area (PDA) (`rules/table1_fonts.py`)

Rule 7 enforces minimum font height for the Net Quantity and MRP declarations based on the Principal Display Area (PDA) of the package.

#### Table-I Statutory Minimum Font Heights
| Band Index | Principal Display Area ($A$ in $\text{cm}^2$) | Normal Minimum Height | Blown / Formed / Molded / Embossed |
| :---: | :--- | :---: | :---: |
| **1** | $A \le 50\text{ cm}^2$ | **1.0 mm** | **1.5 mm** |
| **2** | $50\text{ cm}^2 < A \le 100\text{ cm}^2$ | **1.5 mm** | **3.0 mm** |
| **3** | $100\text{ cm}^2 < A \le 500\text{ cm}^2$ | **2.5 mm** | **4.0 mm** |
| **4** | $500\text{ cm}^2 < A \le 2500\text{ cm}^2$ | **4.0 mm** | **6.0 mm** |
| **5** | $A > 2500\text{ cm}^2$ | **6.0 mm** | **6.0 mm** |

#### PDA Calculation Formulas (Rule 7(4))
- **Rectangular / Flat package:** $\text{PDA} = \text{Height} \times \text{Width}$
- **Cylindrical / Bottle package:** $\text{PDA} = 0.40 \times \text{Height} \times (\pi \times \text{Diameter})$
- **Other shapes / Total Surface:** $\text{PDA} = 0.40 \times \text{Total Surface Area}$

#### Decision Criteria
- Height Tolerance: $\text{FONT\_TOL\_MM} = 0.1\text{ mm}$.
- Evaluated separately on `net_qty` and `mrp`.
- If PDA is not computed (calibration unavailable and no dimensions supplied): **`NA`** (*"PDA not computed — font heights not evaluated."*)
- If font height cannot be measured: **`NA`** (*"<Field> font height not measured."*)
- If $\text{Measured Height} \ge (\text{Required Height} - 0.1\text{ mm})$: **`PASS`**
- If $\text{Measured Height} < (\text{Required Height} - 0.1\text{ mm})$: **`FAIL`**

---

### Rule 7(3): Character Width-to-Height Ratio (`rules/table1_fonts.py`)

Requires that the width of every letter and numeral shall not be less than one-third of its height.

#### Statutory Exemption
The characters `'1'`, `'i'`, `'I'`, and `'l'` are narrow by nature and exempt from the aspect ratio check.

#### Decision Logic
$$\text{Width} \ge \frac{\text{Height}}{3}$$
- If all measured glyphs satisfy the ratio: **`PASS`** (*"All measured characters satisfy width >= height/3."*)
- If any non-exempt glyph has $\text{width} < \text{height} / 3$: **`FAIL`** (*"Character width below height/3 (Rule 7(3)): '<glyph>' <W>x<H> mm..."*)

---

## 3. Deep-Dive Audit: 12 Latent Issues, Bugs & Edge Cases

The following 12 issues were uncovered during static analysis of the parsing, regex, extraction, and rule evaluation pipelines.

---

### Issue 1: False Rule 13 Violations from Company Names & Postal Addresses

* **Source File:** `core/netra_core/stages/s6_metrology.py`, Line 113–120  
* **Sub-module:** `core/netra_core/rules/si_units.py`, Line 23–26 (`_PROHIBITED_RE`)  
* **Severity:** **HIGH** (Causes legitimate packages to be falsely prosecuted)

#### Detailed Mechanism
In `s6_metrology.py`:
```python
hit = None
for key in ctx.fields:
    raw = _raw(ctx, key)
    if raw:
        hits = find_prohibited_units(raw)
        if hits:
            hit = (key, hits[0])
            break
```
The check iterates over **all extracted fields**, including `mfg_address` and `consumer_care`. 
The regex `_PROHIBITED_RE` checks `\b(gms|grm|kilo|kgs|ltr|cc|cu\.?\s*cm|pkts|doz)\b`.

#### Failure Scenario
1. A manufacturer is located at `"Plot 12, GMS Industrial Area, Bangalore 560001"` or `"LTR Logistics Park"`.
2. A company is named `"KGS Agro Foods Pvt Ltd"` or customer care email is `"care@kgsfoods.com"`.
3. `find_prohibited_units` matches `"gms"`, `"ltr"`, or `"kgs"`.
4. Stage 6 immediately flags **Rule 13 as `FAIL`**:
   > *"Prohibited unit syntax 'gms' in Manufacturer Address — statutory symbol 'g' required."*
5. The entire inspection verdict flips to `VIOLATION`.

#### Recommended Remediation (For Future Action)
Restrict Rule 13 evaluation exclusively to quantity-bearing fields: `("net_qty", "usp")`. Alternatively, ignore matches that occur inside recognized email strings, URL strings, or postal address tokens.

---

### Issue 2: Pipeline Crash (`ValueError`) on Area/Sheet Net Quantities in USP Engine

* **Source File:** `core/netra_core/rules/usp.py`, Line 88–90  
* **Triggering Call:** `core/netra_core/stages/s6_metrology.py`, Line 153–156  
* **Severity:** **CRITICAL** (Crashes python engine; scan terminates in `RETRY` / Error)

#### Detailed Mechanism
In `si_units.py`, area units `cm2` and `m2` are defined as `PERMITTED_UNITS`. Packages for aluminium foil, cling wrap, tiles, and paper sheets declare net quantity in area (`e.g. Net Qty: 2.5 m2` or `100 cm2`).
However, in `rules/usp.py`:
```python
_BASE = {
    "mg": ("mass", Decimal("0.000001")),
    "g": ("mass", Decimal("0.001")),
    "kg": ("mass", Decimal("1")),
    "ml": ("volume", Decimal("0.001")),
    "cl": ("volume", Decimal("0.01")),
    "l": ("volume", Decimal("1")),
    "mm": ("length", Decimal("0.001")),
    "cm": ("length", Decimal("0.01")),
    "m": ("length", Decimal("1")),
}
```
If a package declares `2 m2`, `evaluate_usp()` reaches line 88:
```python
if dim in _BASE:
    ...
elif dim in _COUNT:
    ...
else:
    raise ValueError(f"unsupported quantity unit: {unit!r}")
```
In `s6_metrology.py`, `evaluate_usp` is called **without a `try...except ValueError` block**:
```python
r = evaluate_usp(
    mrp_val, qty_val, qty_unit,
    declared=declared.value if declared is not None else None,
    declared_unit=declared.unit if declared is not None else None)
```

#### Failure Scenario
Scanning any commodity declaring area (`m2`, `cm2`) raises an unhandled `ValueError`, crashing Stage 6. The app receives an `INTERNAL` pipeline error and tells the inspector to retry indefinitely.

#### Recommended Remediation (For Future Action)
Add `"cm2"` and `"m2"` to `_BASE` in `usp.py` with statutory reference unit (`per sq. metre` or `per cm2`), or catch `ValueError` in `s6_metrology.py` and output `CheckStatus.NA` with an informative note.

---

### Issue 3: Missing "PKD" / "PKD." Date Anchors Rejecting Standard Indian Packs

* **Source File:** `core/netra_core/stages/s5_field_extract.py`, Line 69–74  
* **Severity:** **HIGH** (False violation rate on FMCG packaging)

#### Detailed Mechanism
In `s5_field_extract.py`:
```python
FIELD_MFG_DATE: (
    r"\bmfg\b", r"\bmfd\b",
    r"\bdate\s+of\s+(?:mfg|manufactur|pack)",
    r"\bmanufactur(?:ed|ing)\s+on\b",
    r"\bpack(?:ed|ing)\s+(?:on|date)\b",
),
```
In India, the abbreviation **`PKD`** or **`PKD.`** (short for Packed) is one of the most widespread statutory date stamp markings across biscuit wrappers, soaps, detergent packs, and snacks (e.g., `PKD. 08/2025` or `PKD 12/24`).
Notice that `_ANCHORS[FIELD_MFG_DATE]` requires `\bpack(?:ed|ing)\s+(?:on|date)\b`, or `\bmfg\b`, or `\bmfd\b`. It **omits `pkd` and `pkd.`**.

#### Failure Scenario
A package stamped `PKD. 10/2025` fails to match any anchor in `FIELD_MFG_DATE`. Stage 5 extracts no date field (`ctx.fields.get("mfg_date") is None`). Stage 6 issues a **`FAIL` on Rule 6(1)(d)**:
> *"Date of manufacture / packing not detected."*

#### Recommended Remediation (For Future Action)
Add `r"\bpkd\.?\b"` and `r"\bpacked\b"` to `_ANCHORS[FIELD_MFG_DATE]`.

---

### Issue 4: Strict 4-Digit Year Requirement Rejecting 2-Digit Date Stamps

* **Source File:** `core/netra_core/rules/parsers.py`, Line 157–163  
* **Severity:** **MEDIUM-HIGH** (Rejects valid industrial date markings)

#### Detailed Mechanism
The date regexes in `parsers.py` are:
```python
_DMY_RE = re.compile(
    r"(?<![0-9])([0-9]{1,2})\s*[/\-.]\s*([0-9]{1,2})\s*[/\-.]\s*([0-9]{4})(?![0-9])")
_MY_RE = re.compile(
    r"(?<![0-9])([0-9]{1,2})\s*[/\-.]\s*([0-9]{4})(?![0-9])")
_MONY_RE = re.compile(
    r"([a-z]{3,9})\s*[\-,. ]{0,3}\s*([0-9]{4})(?![0-9])", re.IGNORECASE)
```
All three patterns explicitly require **`[0-9]{4}`** (4-digit year).

#### Failure Scenario
Industrial dot-matrix printers and hot-foil stamps frequently print `MFD 08/25`, `09/26`, or `OCT 25` to save printhead space. 
Because `parse_date()` encounters a 2-digit year, all regexes return `None`. Stage 6 emits **`FAIL` on Rule 6(1)(d)**:
> *"Date '08/25' is not in a statutory form (MM/YYYY, Month YYYY, or DD/MM/YYYY) — Rule 6(1)(d)."*

#### Recommended Remediation (For Future Action)
Support 2-digit years `([0-9]{2}|[0-9]{4})` with pivot logic (e.g., $2000 + yy$ for $yy < 70$).

---

### Issue 5: Missing "Net Vol." / "Net Volume" Anchor Rejecting Liquid Products

* **Source File:** `core/netra_core/stages/s5_field_extract.py`, Line 57–60  
* **Severity:** **MEDIUM** (Rejects beverages, oils, and liquid personal care)

#### Detailed Mechanism
In `s5_field_extract.py`:
```python
FIELD_NET_QTY: (
    r"\bnet\s*(?:quantity|qty|qnty|wt|weight|contents?)\b",
    r"^(?:quantity|qty)\b",
),
```
For liquids, standard packaging often states:
- `"Net Vol. 750 ml"`
- `"Net Volume: 1 Litre"`

`_ANCHORS[FIELD_NET_QTY]` requires `quantity`, `qty`, `qnty`, `wt`, `weight`, or `contents`. It does **not** include `vol` or `volume`.

#### Failure Scenario
Bottles of mineral water, juices, and shampoo stating `"Net Vol. 500 ml"` do not match the anchor. Stage 5 ignores the token. Rule 6(1)(c) fails with:
> *"Net quantity declaration not detected."*

#### Recommended Remediation (For Future Action)
Update anchor regex to: `r"\bnet\s*(?:quantity|qty|qnty|wt|weight|vol(?:ume)?|contents?)\b"`.

---

### Issue 6: Decimal USP Stealing MRP Value in `parse_money_lenient`

* **Source File:** `core/netra_core/rules/parsers.py`, Line 130–133  
* **Severity:** **HIGH** (Corrupts MRP and causes false USP math failure)

#### Detailed Mechanism
In `parsers.py`:
```python
def parse_money_lenient(text: str) -> Optional[Decimal]:
    marked = parse_money(text)
    if marked is not None:
        return marked
    ...
    matches = list(_BARE_AMOUNT_RE.finditer(t[kw.end():]))
    if not matches:
        return None
    best = next((m for m in matches
                 if re.fullmatch(r"[0-9]+\.[0-9]{2}", m.group(0))),
                matches[0])
    return _num(best.group(0))
```
When OCR does not recognize the rupee symbol (`₹`), `parse_money_lenient` is invoked. It scans tokens after `MRP`. If multiple bare numbers exist, it **prioritizes numbers with two decimal places** (`[0-9]+\.[0-9]{2}`).

#### Failure Scenario
Consider an FMCG label printed as:
`"MRP Rs 100 (incl. of all taxes) USP 0.50 / g"`
- `100` is an integer (no decimals).
- `0.50` has two decimal places.
- `parse_money_lenient` iterates through matches `[100, 0.50]`, finds that `0.50` matches `[0-9]+\.[0-9]{2}`, and **returns `0.50` as the MRP**!
- Then `evaluate_usp(mrp=0.50, qty=200g)` calculates expected USP as `0.50 / 200 = 0.0025`.
- Declared USP `0.50` is compared to `0.0025`, resulting in a massive delta and a **`FAIL` on Rule 6(11)** (*USP math error*).

#### Recommended Remediation (For Future Action)
Pick the **first** number immediately following the MRP anchor, or explicitly stop scanning if a `USP` anchor boundary is encountered.

---

### Issue 7: Overly Strict Tax Phrasing Rejecting Common Formulations

* **Source File:** `core/netra_core/rules/declarations.py`, Line 55–56  
* **Severity:** **MEDIUM** (Triggers false violations on compliant goods)

#### Detailed Mechanism
In `declarations.py`:
```python
_TAX_PHRASE_RE = re.compile(
    r"incl(?:usive)?\.?\s*(?:of\s+)?all\s+taxes?", re.IGNORECASE)
```
This regex strictly mandates the word **`all`**.

#### Failure Scenario
Many manufacturers print:
- `"INCL. OF TAXES"`
- `"INCLUSIVE OF TAXES"`
- `"INCL. GST"`
- `"INCLUSIVE OF ALL APPLICABLE TAXES"`

Because the word `"all"` is either missing or has an intervening word `"applicable"`, `_TAX_PHRASE_RE.search(t)` returns `None`. Rule 6(1)(e) issues a **`FAIL`**:
> *"MRP non-compliant — missing statutory phrase 'inclusive of all taxes'."*

#### Recommended Remediation (For Future Action)
Allow `r"incl(?:usive)?\.?\s*(?:of\s+)?(?:all\s+)?(?:applicable\s+)?taxes?"` and `r"incl(?:usive)?\.?\s*gst"`.

---

### Issue 8: Spatial Anchor Overwrite on Multi-Entity Addresses

* **Source File:** `core/netra_core/stages/s5_field_extract.py`, Line 270–280  
* **Severity:** **MEDIUM-HIGH** (Produces false packer/manufacturer separation errors)

#### Detailed Mechanism
In `s5_field_extract.py`:
```python
for cand in candidates:
    ...
    if val is not None:
        accepted[spec.key] = val
        break
```
Stage 5 iterates over anchor candidates and accepts the **first** match that parses.
Modern packaged products frequently have two separate address blocks:
1. `"Marketed by: ABC Consumer Care Ltd, Mumbai 400001"` (at top of panel)
2. `"Manufactured by: XYZ Contract Packers, Solan 173212"` (at bottom of panel)

#### Failure Scenario
If the "Marketed by" block appears first in reading order, Stage 5 accepts it as `mfg_address` and terminates the loop (`break`).
The "Manufactured by" block is never parsed.
Then in `s6_metrology.py` -> `decl.check_address()`:
```python
has_mfr = bool(_MFR_RE.search(t))
third_party = bool(_PACKER_RE.search(t) or _MARKETER_RE.search(t))
if third_party and not has_mfr:
    return DeclarationResult(
        False,
        "Packer / marketer is named without manufacturer details — Rule 6(1)(a)...")
```
Because only the marketer was captured, `has_mfr` is `False`, and NETRA flags a **`FAIL` on Rule 6(1)(a)**, claiming the manufacturer was omitted when it was present on the package.

#### Recommended Remediation (For Future Action)
Aggregate all address paragraph blocks or search for both manufacturer and marketer blocks into a unified address context.

---

### Issue 9: Imported Products Failing Address Check When Naming Importer/Marketer

* **Source File:** `core/netra_core/rules/declarations.py`, Line 115–121  
* **Severity:** **MEDIUM**

#### Detailed Mechanism
In `declarations.py`:
```python
has_mfr = bool(_MFR_RE.search(t))
third_party = bool(_PACKER_RE.search(t) or _MARKETER_RE.search(t))
if third_party and not has_mfr:
    return DeclarationResult(
        False,
        "Packer / marketer is named without manufacturer details — Rule 6(1)(a) "
        "requires both when a third party packs the commodity.",
        pin=pin)
```
For imported commodities, the statutory obligation under Rule 6(1)(a) requires the name and address of the **Importer** in India. The overseas manufacturer's full address is not subject to Indian PIN code rules.

#### Failure Scenario
An imported pack states:
`"Imported & Marketed by: Sony India Pvt Ltd, Mohan Cooperative Industrial Estate, New Delhi 110044."`
`_MARKETER_RE` triggers `third_party = True`.
`_MFR_RE` finds no domestic manufacturer (`has_mfr = False`).
NETRA incorrectly fails Rule 6(1)(a) for missing manufacturer details, despite it being a legally compliant imported item.

#### Recommended Remediation (For Future Action)
If `looks_imported()` is true or `importer` is named, exempt the pack from the dual manufacturer/packer requirement.

---

### Issue 10: Evidence Bounding Box Disconnect When OCR Fails on Present Fields

* **Source File:** `core/netra_core/stages/s6_metrology.py`, Line 70–74 & 86–87  
* **Mobile File:** `apps/mobile/lib/features/report/widgets/evidence_viewer.dart`, Line 42–56  
* **Severity:** **HIGH** (Direct cause of user-reported bug: *"even if everything is present then too in evidence it shows its missing"*)

#### Detailed Mechanism
In `s6_metrology.py`:
```python
def _evidence(ctx: PipelineContext, key: Optional[str]):
    if key is None:
        return None
    fv = ctx.fields.get(key)
    return fv.bbox if fv is not None else None
```
When Stage 5 fails to detect a field (e.g. due to lighting, anchor omission, or OCR misread), `ctx.fields.get(key)` is `None`.
Stage 6 marks the rule as `FAIL`, and sets `evidence_bbox = None`.
In the Flutter mobile app (`evidence_viewer.dart` and `check_tile.dart`):
```dart
if (check.evidenceBbox == null) {
  // Renders grey banner: "No spatial evidence recorded"
}
```

#### Failure Scenario
The inspector holds a physical package with the Net Quantity printed on it. Because OCR slightly missed the anchor, NETRA marks Net Quantity as **FAIL: Net quantity declaration not detected**, and the evidence viewer shows **NO BOUNDING BOX** (null).
The inspector is left confused: the text is right there on the pack, but the app claims it is missing and refuses to highlight where it looked or why it failed.

#### Recommended Remediation (For Future Action)
When a field check fails due to non-detection, attach a candidate region or the closest anchor token bbox as `evidence_bbox` so the inspector can see what the engine evaluated.

---

### Issue 11: Font Height Overestimation from Full Text Bounding Box

* **Source File:** `core/netra_core/stages/s5_field_extract.py`, Line 332–335  
* **Severity:** **MEDIUM** (Risks false PASS on undersized typography)

#### Detailed Mechanism
In `s5_field_extract.py`:
```python
# rough line-height fallback from the token bbox height
ctx.font_heights[key] = fv.bbox.h * ctx.mm_per_px
```
Rule 7 Table-I prescribes minimum height for the **numeral glyphs** (capital letters and numerals: height of 'A' or '1').
`fv.bbox.h` represents the height of the entire multi-word token box (e.g., `"Net Qty: 100g"`).
This includes:
- Line bounding box padding
- Ascenders (e.g., 't', 'd', 'l') and Descenders (e.g., 'y', 'g', 'p')
- OCR bounding box margin

#### Failure Scenario
On a package requiring a $2.5\text{ mm}$ numeral height, the actual numerals are $2.1\text{ mm}$ (a legal violation). However, because `fv.bbox.h` includes the descender of `y` and ascender of `t`, the total box height measures $2.6\text{ mm}$.
NETRA marks Rule 7 as **`PASS`**, missing a genuine statutory violation.

#### Recommended Remediation (For Future Action)
Measure font height strictly from isolated numeral glyph contours in the binarized crop rather than using the full line-level token bounding box.

---

### Issue 12: Generic Product Name Conflation with Brand Trademarks

* **Source File:** `core/netra_core/stages/s5_field_extract.py`, Line 305–325  
* **Severity:** **LOW-MEDIUM** (Semantic inaccuracy in inspection records)

#### Detailed Mechanism
In `s5_field_extract.py`:
```python
# Pick the tallest token in the upper 65% of the package as product name
top_tokens = [t for t in ctx.tokens if t.bbox.y < max_y]
tallest = max(top_tokens, key=lambda t: t.bbox.h)
```
Under Rule 6(1)(b), the declaration must be the **generic or common name** of the commodity (e.g. *"Whole Wheat Atta"*, *"Toothpaste"*, *"Washing Powder"*).
The tallest, largest text at the top of an Indian retail pack is virtually always the **Brand Name / Trademark** (e.g. *"AASHIRVAAD"*, *"COLGATE"*, *"SURF EXCEL"*).

#### Failure Scenario
NETRA extracts the brand name `"OREO"` as the product name. In `s6_metrology.py`, it marks Rule 6(1)(b) as `PASS`:
> *"Common / generic name present — semantic adequacy needs manual review."*
While it flags the need for manual review, the dossier records `"OREO"` as the commodity name rather than `"Chocolate Sandwich Biscuits"`.

#### Recommended Remediation (For Future Action)
Filter out tokens that match trademark registration symbols (®, ™) or known brand entities, and search for standard Food/Commodity category descriptors.

---

## 4. Evidence Linking & UI Display Verification

### Why "Missing" Shows Even When Physically Present
The mobile client receives the scan result as JSON containing `checks`:
```json
{
  "rule": "6(1)(c)",
  "status": "FAIL",
  "message": "Net quantity declaration not detected.",
  "evidence_bbox": null
}
```
1. **Root Cause:** If any anchor in `s5_field_extract.py` fails to match (e.g. `PKD` instead of `MFG`, or `Net Vol` instead of `Net Qty`), Stage 5 creates no field entry in `ctx.fields`.
2. **Cascade to Stage 6:** Stage 6 queries `_raw(ctx, "field_name")`. When it receives `None`, it automatically creates a `FAIL` check with `field=None` or `evidence_bbox=None`.
3. **Mobile Client Presentation:** When `evidence_bbox` is null, Flutter cannot draw a green or red bounding box over the camera image. It renders a neutral check tile with the message *"declaration not detected"*. To the inspector looking at the actual bottle or carton, this appears as though the app is broken or blind to visible text.

---

## 5. Summary Matrix of Checks & Failure Modes

| Statutory Rule | Primary Trigger / Check | Verdict | Common Failure Mode / Latent Bug |
| :--- | :--- | :---: | :--- |
| **Rule 26** | Qty $\le 10\text{ g}/10\text{ mL}$, Bulk $> 25\text{ kg}$, Institutional | `NA` | Tobacco small packs falsely exempted if commodity name not recognized. |
| **Rule 13** | Prohibited symbols: `gms, kgs, ltr, cc, pkts` | `PASS` / `FAIL` | **False Positive:** Company addresses with "GMS Road" or "LTR Corp" trigger FAIL. |
| **Rule 6(1)(c)** | Standard SI unit & number | `PASS` / `FAIL` | **False Negative:** Fails to detect liquids declared as "Net Vol. 500 ml". |
| **Rule 6(1)(e)** | MRP keyword + Rupee amount + 'incl. of all taxes' | `PASS` / `FAIL` | **False Positive:** Rejects "Incl. of taxes" or "Incl. GST" without word "all". |
| **Rule 6(11)** | USP = MRP / Qty (within $\pm \text{Rs } 0.01$) | `PASS` / `FAIL` / `NA` | **Engine Crash:** Throws unhandled `ValueError` on area units (`m2`, `cm2`). |
| **Rule 6(1)(d)** | Mfg/Packing Date in statutory format | `PASS` / `FAIL` | **False Negative:** Omits `PKD.` anchor; rejects 2-digit years (`08/25`). |
| **Rule 6(1)(a)** | Manufacturer & Packer + 6-digit PIN code | `PASS` / `FAIL` | **False Positive:** Multi-entity addresses overwrite manufacturer with marketer. |
| **Rule 6(1)(aa)** | Explicit country name on imported packs | `PASS` / `FAIL` / `NA` | Fails imported products when importer is listed without overseas manufacturer. |
| **Rule 6(1)(n)** | Phone + Email + Postal Address / PIN | `PASS` / `FAIL` | Toll-free variations or spaced STD codes occasionally miss regex. |
| **Rule 6(1)(b)** | Common / generic product name | `PASS` / `FAIL` | Conflates brand trademark (tallest token) with generic product category. |
| **Rule 7** | Min font height (1.0 to 6.0 mm) by PDA band | `PASS` / `FAIL` / `NA` | **Overestimation:** Uses total line bbox height instead of numeral height. |
| **Rule 7(3)** | Glyph aspect ratio $\ge 1/3$ (exempt `1, i, I, l`) | `PASS` / `FAIL` | Rarely fails unless font glyph extraction is corrupted. |

---
*End of Audit Report. No code files were modified during this analysis.*
