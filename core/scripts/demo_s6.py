"""NETRA — Stage 6 demo: the full statutory checklist from decoded fields.

Simulates the state after OCR + field extraction (Stages 4-5): builds a
PipelineContext from label text and runs the deterministic metrology
engine. Five statutory traps are planted — the exact sub-visual
non-compliances SIH26034 targets.

Run:  python scripts/demo_s6.py
"""
from netra_core.context import FieldValue, PipelineContext
from netra_core.rules.citations import citation
from netra_core.stages import s6_metrology

LABEL = {
    "product_name":  "Instant Masala Noodles",
    "net_qty":       "Net Quantity: 70 gms",        # trap: prohibited syntax
    "mrp":           "MRP ₹ 14.00",                 # trap: tax phrase missing
    "usp":           "Unit Sale Price ₹ 0.35 / g",  # trap: corrupted math
    "mfg_date":      "MFG 08/2026",
    "mfg_address":   "Imported by: Global Foods, Mumbai 400001",
    "origin":        "Made in PRC",                 # trap: ambiguous origin
    "consumer_care": "Consumer Care: Global Foods, Tel: 1800-123-4567",
}


def main() -> None:
    ctx = PipelineContext(shape_hint="pouch")
    ctx.fields = {k: FieldValue(raw=v) for k, v in LABEL.items()}
    ctx.pda_cm2 = 80.0                               # band 2 -> 1.5 mm minimum
    ctx.font_heights = {"net_qty": 1.2, "mrp": 1.6}  # trap: net qty too small

    s6_metrology.run(ctx)

    stage = ctx.stages[-1]
    print(f"NETRA verdict: {ctx.verdict.value}   "
          f"(stage 6 took {stage.duration_ms:.2f} ms)\n")
    for c in ctx.checks:
        print(f"  [{c.status.value:>4}] {c.rule:<8} {c.message}")
    print()
    for c in ctx.failed_checks:
        print(f"  citation> {citation(c.rule)}")


if __name__ == "__main__":
    main()
