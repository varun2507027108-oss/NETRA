"""NETRA — pure-logic demo: full statutory verdict from label text alone.

Run:  python scripts/demo_rules.py
(This is exactly what Stage 6 will automate — assembled manually here
until s6_metrology lands, so you can see the engine work today.)
"""
from netra_core.context import CheckStatus, PipelineContext
from netra_core.rules.citations import citation
from netra_core.rules.exemptions import assess_exemption
from netra_core.rules.parsers import parse_date, parse_money, parse_quantity, parse_usp
from netra_core.rules.si_units import find_prohibited_units
from netra_core.rules.usp import evaluate_usp

LABEL = {
    "mrp":      "MRP ₹ 50.00 (incl. of all taxes)",
    "net_qty":  "Net Quantity: 200 gms",          # <- deliberate violation
    "usp":      "Unit Sale Price ₹ 0.25 / g",
    "mfg_date": "MFG 08/2026",
}


def main() -> None:
    ctx = PipelineContext(shape_hint="pouch")
    qty = parse_quantity(LABEL["net_qty"])
    mrp = parse_money(LABEL["mrp"])
    usp = parse_usp(LABEL["usp"])

    # Rule 13 — prohibited unit syntax (automatic violation)
    hits = find_prohibited_units(LABEL["net_qty"])
    if hits:
        ctx.add_check("13", CheckStatus.FAIL,
                      f"Prohibited unit '{hits[0].token}' — use '{hits[0].suggestion}' "
                      f"({citation('13')})")
    else:
        ctx.add_check("13", CheckStatus.PASS, "Unit syntax compliant (Rule 13).")

    # Rule 6(1)(d) — date of manufacture
    if parse_date(LABEL["mfg_date"]):
        ctx.add_check("6(1)(d)", CheckStatus.PASS, "MFG date in MM/YYYY form.")
    else:
        ctx.add_check("6(1)(d)", CheckStatus.FAIL, "Date of manufacture missing/malformed.")

    # Rule 6(11) — USP math (note: qty is parsed as a clean 200 g)
    if qty and mrp:
        r = evaluate_usp(mrp, qty.value, qty.unit,
                         declared=usp.value if usp else None,
                         declared_unit=usp.unit if usp else None)
        ctx.add_check("6(11)",
                      CheckStatus.PASS if r.compliant else CheckStatus.FAIL, r.detail)

    # Rule 26 — exemption screen
    ex = assess_exemption(qty.value if qty else 0, qty.unit if qty else "")
    if ex.exempt:
        ctx.add_check("26", CheckStatus.NA, ex.note)

    print(f"NETRA verdict: {ctx.verdict.value}\n")
    for c in ctx.checks:
        print(f"  [{c.status.value:>4}] {c.rule:<7} {c.message}")


if __name__ == "__main__":
    main()
