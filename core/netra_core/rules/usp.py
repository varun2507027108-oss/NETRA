"""Rule 6(11) — Unit Sale Price engine.

Determines the statutory *reference unit* from the net quantity, computes
the expected USP (MRP / net qty in that unit), and validates a declared
USP against it with a 1-paisa (Rs 0.01) tolerance. Decimal arithmetic only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from ..config import USP_TOLERANCE
from .parsers import to_decimal

TOLERANCE = Decimal(USP_TOLERANCE)
_CENT = Decimal("0.01")

# canonical unit -> (dimension, factor to the dimension's main unit)
_BASE = {
    "mg": ("mass", Decimal("0.000001")),
    "g":  ("mass", Decimal("0.001")),
    "kg": ("mass", Decimal("1")),
    "ml": ("volume", Decimal("0.001")),
    "cl": ("volume", Decimal("0.01")),
    "L":  ("volume", Decimal("1")),
    "mm": ("length", Decimal("0.001")),
    "cm": ("length", Decimal("0.01")),
    "m":  ("length", Decimal("1")),
}
_MAIN = {"mass": "kg", "volume": "L", "length": "m"}
_SUB = {"mass": ("g", Decimal("1000")),
        "volume": ("ml", Decimal("1000")),
        "length": ("cm", Decimal("100"))}
_COUNT = {"n", "u", "piece", "pair", "set"}
_ONE_UNIT = {"mass": "kg", "volume": "litre", "length": "metre", "count": "unit"}


@dataclass(frozen=True)
class USPResult:
    exempt: bool
    required_unit: Optional[str]
    expected: Optional[Decimal]      # statutory USP, 2 dp (for the report)
    expected_raw: Optional[Decimal]  # MRP / qty, unrounded (tolerance basis)
    declared: Optional[Decimal]
    declared_unit: Optional[str]
    unit_ok: Optional[bool]
    math_ok: Optional[bool]
    delta: Optional[Decimal]
    compliant: bool
    detail: str


def evaluate_usp(mrp, net_qty, qty_unit, declared=None, declared_unit=None) -> USPResult:
    mrp_d = to_decimal(mrp)
    qty = to_decimal(net_qty)
    if mrp_d <= 0:
        raise ValueError(f"MRP must be positive, got {mrp_d}")
    if qty <= 0:
        raise ValueError(f"net quantity must be positive, got {qty}")

    unit = (qty_unit or "").strip()
    declared_d = to_decimal(declared) if declared not in (None, "") else None
    du = (declared_unit or "").strip().lower() or None

    # ---- dimension & reference-unit selection -----------------------------
    if unit in _COUNT or unit == "number":
        dim, base, qty_in_req = "count", qty, qty
        exempt = qty == 1                       # second proviso
        required = None if exempt else "piece"
        raw = mrp_d if exempt else mrp_d / qty
    elif unit in _BASE:
        dim, factor = _BASE[unit]
        base = qty * factor
        if base == 1:                           # exactly 1 kg / 1 L / 1 m
            exempt, required, qty_in_req = True, None, qty
            raw = mrp_d
        elif base < 1:                          # < 1 kg/L/m -> per g/ml/cm
            exempt = False
            required = _SUB[dim][0]
            qty_in_req = base * _SUB[dim][1]
            raw = mrp_d / qty_in_req
        else:                                   # > 1 kg/L/m -> per kg/L/m
            exempt = False
            required = _MAIN[dim]
            qty_in_req = base
            raw = mrp_d / qty_in_req
    else:
        raise ValueError(f"unsupported quantity unit: {unit!r}")

    expected = raw.quantize(_CENT, rounding=ROUND_HALF_UP)

    if exempt:
        return USPResult(True, None, expected, raw, declared_d, declared_unit,
                         None, None, None, True,
                         f"Second proviso to Rule 6(11): net quantity is exactly one "
                         f"{_ONE_UNIT[dim]} -> RSP itself is the USP; separate "
                         f"declaration not required.")

    if declared_d is None:
        return USPResult(False, required, expected, raw, None, declared_unit,
                         None, None, None, False,
                         f"USP not declared. Statutory requirement: Rs {expected} "
                         f"per {required} (MRP / net quantity, Rule 6(11)).")

    if required == "piece":
        unit_ok = du in _COUNT or du == "number"
    else:
        unit_ok = du == required.lower()
    delta = abs(declared_d - raw)
    math_ok = delta <= TOLERANCE
    compliant = unit_ok and math_ok

    notes = []
    if not unit_ok:
        notes.append(f"wrong reference unit — declared '{du or '—'}', statutory "
                     f"'{required}' for this net quantity")
    if not math_ok:
        notes.append(f"USP math error — declared Rs {declared_d} vs calculated "
                     f"Rs {expected} per {required} (tolerance Rs {TOLERANCE})")
    if not notes:
        notes.append(f"USP Rs {declared_d} per {required} matches MRP / net "
                     f"quantity within Rs {TOLERANCE}")

    return USPResult(False, required, expected, raw, declared_d, declared_unit,
                     unit_ok, math_ok, delta, compliant, "; ".join(notes))
