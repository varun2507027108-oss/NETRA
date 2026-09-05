"""Rule 26 — statutory exemptions from the Packaged Commodities Rules."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .parsers import to_decimal

SMALL_LIMIT = Decimal("10")               # g or mL, inclusive
BULK_LIMIT = Decimal("25")                # kg or L, exclusive
CEMENT_FERT_BULK_LIMIT = Decimal("50")    # kg, exclusive

_TO_GRAM = {"mg": Decimal("0.001"), "g": Decimal("1"), "kg": Decimal("1000")}
_TO_ML = {"ml": Decimal("1"), "cl": Decimal("10"), "L": Decimal("1000")}
_TO_KG = {"mg": Decimal("0.000001"), "g": Decimal("0.001"), "kg": Decimal("1")}
_TO_L = {"ml": Decimal("0.001"), "cl": Decimal("0.01"), "L": Decimal("1")}

_TOBACCO_FAMILY = ("tobacco", "bidi", "pan masala", "panmasala")
_BULK_EXCEPTIONS = ("cement", "fertiliser", "fertilizer")


@dataclass(frozen=True)
class Exemption:
    exempt: bool
    clause: Optional[str]
    note: str


def _mentions(commodity: str, needles) -> bool:
    c = (commodity or "").lower()
    return any(n in c for n in needles)


def assess_exemption(net_qty, unit: str, commodity: str = "",
                     *, institutional: bool = False, fast_food: bool = False) -> Exemption:
    """Evaluate Rule 26 in statutory priority order."""
    if institutional:
        return Exemption(True, "Rule 26 — institutional / industrial supply",
                         "Supplied directly to an institutional or industrial consumer.")
    if fast_food:
        return Exemption(True, "Rule 26 — fast food packaging",
                         "Packaged by a restaurant / hotel / canteen.")

    qty = to_decimal(net_qty)
    u = (unit or "").strip()

    # small packages: net <= 10 g or <= 10 mL (tobacco family excluded)
    g = qty * _TO_GRAM[u] if u in _TO_GRAM else None
    ml = qty * _TO_ML[u] if u in _TO_ML else None
    if (g is not None and g <= SMALL_LIMIT) or (ml is not None and ml <= SMALL_LIMIT):
        if _mentions(commodity, _TOBACCO_FAMILY):
            return Exemption(False, None, "Small-package exemption denied: "
                             "tobacco / bidi / pan masala are excluded.")
        return Exemption(True, "Rule 26 — small package",
                         f"Net quantity <= 10 {'g' if g is not None else 'mL'}.")

    # bulk packages
    kg = qty * _TO_KG[u] if u in _TO_KG else None
    litres = qty * _TO_L[u] if u in _TO_L else None
    if _mentions(commodity, _BULK_EXCEPTIONS):
        if kg is not None and kg > CEMENT_FERT_BULK_LIMIT:
            return Exemption(True, "Rule 26 — bulk (cement/fertilizer carve-out)",
                             f"{kg} kg exceeds the 50 kg threshold for {commodity!r}.")
        if kg is not None and BULK_LIMIT < kg <= CEMENT_FERT_BULK_LIMIT:
            return Exemption(False, None,
                             f"{kg} kg: cement / fertilizer up to 50 kg are NOT exempt.")
    elif (kg is not None and kg > BULK_LIMIT) or (litres is not None and litres > BULK_LIMIT):
        return Exemption(True, "Rule 26 — bulk package",
                         f"Net quantity exceeds 25 {'kg' if kg is not None else 'L'}.")

    return Exemption(False, None,
                     "No Rule 26 exemption applies; all Rule 6 declarations required.")
