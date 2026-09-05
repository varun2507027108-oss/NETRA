"""Human-readable statutory citations used in checks and PDF dossiers."""

CITATIONS = {
    "6(1)(a)":  "Rule 6(1)(a), LMPC Rules 2011 — name & complete postal address of manufacturer / packer / importer, incl. 6-digit PIN.",
    "6(1)(aa)": "Rule 6(1)(aa), LMPC Rules 2011 — country of origin, explicit (no ambiguous abbreviations).",
    "6(1)(b)":  "Rule 6(1)(b), LMPC Rules 2011 — common / generic name of the commodity.",
    "6(1)(c)":  "Rule 6(1)(c), LMPC Rules 2011 — net quantity in standard metric units.",
    "6(1)(d)":  "Rule 6(1)(d), LMPC Rules 2011 — month & year of manufacture / packing / import (MM/YYYY or Month YYYY).",
    "6(1)(e)":  "Rule 6(1)(e), LMPC Rules 2011 — MRP with 'inclusive of all taxes' phrasing.",
    "6(1)(n)":  "Rule 6(1)(n), LMPC Rules 2011 — consumer care details (name, address, helpline, email).",
    "6(10)":    "Rule 6(10), LMPC Rules 2011 — e-commerce listing declarations.",
    "6(11)":    "Rule 6(11), LMPC Rules 2011 — Unit Sale Price declaration and reference units.",
    "7":        "Rule 7 & Table-I (G.S.R. 629(E)), LMPC Rules 2011 — minimum numeral/letter height by PDA band.",
    "7(3)":     "Rule 7(3), LMPC Rules 2011 — character width >= height/3 (except 1, i, I, l).",
    "7(4)":     "Rule 7(4), LMPC Rules 2011 — Principal Display Area computation.",
    "13":       "Rule 13, LMPC Rules 2011 — standard metric unit symbols; prohibited syntax (gms, ltr, cc, ...).",
    "26":       "Rule 26, LMPC Rules 2011 — statutory exemptions (small / bulk / institutional / fast food).",
}


def citation(key: str) -> str:
    return CITATIONS.get(key, key)
