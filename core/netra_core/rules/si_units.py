"""Rule 13 — metric unit syntax.

Two distinct jobs:
1. find_prohibited_units(): flag *prohibited* symbols (gms, ltr, cc ...) —
   automatic violations per SIH26034 section 2.4.
2. is_permitted(): membership in the statutory permitted set. Used when a
   unit is present but NOT in the prohibited list (e.g. 'gm', 'nos'):
   Stage 6 decides FAIL vs NA; this module only reports facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parsers import normalize

PERMITTED_UNITS = frozenset({
    "mg", "g", "kg", "ml", "l", "mm", "cm", "m", "cm2", "m2",
    "n", "u", "piece", "pair", "set",
})

# gms | grm | kilo | kgs | ltr | cc | cu.cm | pkts | doz
_PROHIBITED_RE = re.compile(
    r"(?<![a-z0-9])(gms|grm|kilo|kgs|ltr|cc|cu\.?\s*cm|pkts|doz)(?![a-z0-9])",
    re.IGNORECASE,
)

_SUGGESTION = {
    "gms": "g", "grm": "g", "kilo": "kg", "kgs": "kg", "ltr": "L",
    "cc": "mL", "cucm": "mL", "pkts": "piece", "doz": "piece",
}


@dataclass(frozen=True)
class UnitHit:
    token: str
    start: int      # span in the *normalised* text
    end: int
    suggestion: str


def find_prohibited_units(text: str) -> list:
    t = normalize(text)
    hits = []
    for m in _PROHIBITED_RE.finditer(t):
        raw = m.group(1)
        key = re.sub(r"[.\s]", "", raw).lower()          # 'cu.cm' / 'cu cm' -> 'cucm'
        hits.append(UnitHit(raw, m.start(1), m.end(1), _SUGGESTION.get(key, "")))
    return hits


def unit_syntax_ok(text: str) -> bool:
    return not find_prohibited_units(text)


def is_permitted(unit: str) -> bool:
    return (unit or "").strip().lower() in PERMITTED_UNITS
