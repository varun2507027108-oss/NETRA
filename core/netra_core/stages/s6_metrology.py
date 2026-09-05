"""Stage 6 — deterministic statutory metrology & math engine (< 1 ms).

The legal brain of NETRA. Consumes Stage 5's field map and Stage 3's
metric calibration; emits one Check per statutory obligation decidable
from decoded text and measurements:

  Rule 6(1)(a)   manufacturer/packer/importer + PIN      rules/declarations
  Rule 6(1)(aa)  country of origin (imported)            rules/declarations
  Rule 6(1)(b)   common/generic name                     rules/declarations
  Rule 6(1)(c)   net quantity in SI units                rules/declarations
  Rule 6(1)(d)   month & year of manufacture             rules/declarations
  Rule 6(1)(e)   MRP + 'inclusive of all taxes'          rules/declarations
  Rule 6(1)(n)   consumer care (tel/email/address)       rules/declarations
  Rule 6(11)     unit sale price math                    rules/usp
  Rule 7 / 7(3)  Table-I font heights + glyph aspect     rules/table1_fonts
  Rule 13        prohibited unit syntax                  rules/si_units
  Rule 26        exemption screen                        rules/exemptions

Rule 6(10) (e-commerce listings) is out of scope for physical scans.
Stdlib + rules only — identical on desktop and on device via Chaquopy.
Designed to run exactly once per PipelineContext.
"""
from __future__ import annotations

import time
from typing import Optional

from ..config import FONT_TOL_MM
from ..context import CheckStatus, PipelineContext
from ..rules import declarations as decl
from ..rules.citations import citation
from ..rules.exemptions import assess_exemption
from ..rules.parsers import parse_money, parse_quantity, parse_usp
from ..rules.si_units import find_prohibited_units
from ..rules.table1_fonts import font_height_ok, glyph_aspect_ok
from ..rules.usp import evaluate_usp

# declarations that Rule 7 subjects to Table-I minimum heights
_FONT_FIELDS = ("net_qty", "mrp")


def _raw(ctx: PipelineContext, key: str) -> Optional[str]:
    fv = ctx.fields.get(key)
    if fv is None or not fv.raw:
        return None
    raw = fv.raw.strip()
    return raw or None


def _money(ctx: PipelineContext):
    fv = ctx.fields.get("mrp")
    if fv is not None and fv.value is not None:
        return fv.value
    raw = _raw(ctx, "mrp")
    return parse_money(raw) if raw else None


def _quantity(ctx: PipelineContext):
    fv = ctx.fields.get("net_qty")
    if fv is not None and fv.value is not None:
        return fv.value, (fv.unit or "")
    raw = _raw(ctx, "net_qty")
    if raw:
        q = parse_quantity(raw)
        if q is not None:
            return q.value, q.unit
    return None, None


def run(ctx: PipelineContext, options: Optional[dict] = None) -> list:
    """Evaluate every statutory check; returns the Checks added by this stage."""
    opts = options or {}
    first = len(ctx.checks)
    t0 = time.perf_counter()

    def add(rule, ok, message):
        status = (CheckStatus.NA if ok is None
                  else CheckStatus.PASS if ok else CheckStatus.FAIL)
        return ctx.add_check(rule, status, message)

    if not ctx.fields:
        ctx.add_stage("s6_metrology", ok=False,
                      error="no fields extracted (Stage 5 produced nothing)")
        return []

    qty_val, qty_unit = _quantity(ctx)
    commodity = opts.get("commodity") or _raw(ctx, "product_name") or ""

    # ---- Rule 26 exemption screen ------------------------------------------
    exemption = None
    if qty_val is not None:
        exemption = assess_exemption(
            qty_val, qty_unit, commodity,
            institutional=bool(opts.get("institutional")),
            fast_food=bool(opts.get("fast_food")))
        ctx.exemption = exemption
    if exemption is not None and exemption.exempt:
        add("26", None,
            f"{exemption.note} Remaining Rule 6 declarations are not applicable.")
        ctx.add_stage("s6_metrology", True, (time.perf_counter() - t0) * 1000.0)
        return ctx.checks[first:]

    # ---- Rule 13: prohibited unit syntax ------------------------------------
    hit = None
    for key in ctx.fields:
        raw = _raw(ctx, key)
        if raw:
            hits = find_prohibited_units(raw)
            if hits:
                hit = (key, hits[0])
                break
    if hit is not None:
        key, h = hit
        add("13", False,
            f"Prohibited unit syntax '{h.token}' in "
            f"{decl.FIELD_LABELS.get(key, key)} — statutory symbol "
            f"'{h.suggestion}' required. {citation('13')}")
    else:
        add("13", True,
            "No prohibited unit symbols (gms, grm, kilo, kgs, ltr, cc, pkts, doz).")

    # ---- Rule 6(1)(c): net quantity ------------------------------------------
    raw = _raw(ctx, "net_qty")
    if raw is None:
        add("6(1)(c)", False, "Net quantity declaration not detected.")
    else:
        r = decl.check_net_quantity(raw)
        add("6(1)(c)", r.ok, r.detail)

    # ---- Rule 6(1)(e): MRP ----------------------------------------------------
    raw = _raw(ctx, "mrp")
    if raw is None:
        add("6(1)(e)", False, "MRP declaration not detected.")
    else:
        r = decl.check_mrp(raw)
        add("6(1)(e)", r.ok, r.detail)

    # ---- Rule 6(11): unit sale price -------------------------------------------
    mrp_val = _money(ctx)
    usp_raw = _raw(ctx, "usp")
    if mrp_val is not None and qty_val is not None:
        declared = parse_usp(usp_raw) if usp_raw else None
        r = evaluate_usp(
            mrp_val, qty_val, qty_unit,
            declared=declared.value if declared is not None else None,
            declared_unit=declared.unit if declared is not None else None)
        add("6(11)", r.compliant, r.detail)
    else:
        add("6(11)", None, "USP not evaluable — MRP or net quantity missing.")

    # ---- Rule 6(1)(d): date of manufacture --------------------------------------
    raw = _raw(ctx, "mfg_date")
    if raw is None:
        add("6(1)(d)", False, "Date of manufacture / packing not detected.")
    else:
        r = decl.check_mfg_date(raw)
        add("6(1)(d)", r.ok, r.detail)

    # ---- Rule 6(1)(a): manufacturer / packer / importer ---------------------------
    raw = _raw(ctx, "mfg_address")
    if raw is None:
        add("6(1)(a)", False,
            "Manufacturer / packer / importer details not detected.")
    else:
        r = decl.check_address(raw)
        add("6(1)(a)", r.ok, r.detail)

    # ---- Rule 6(1)(aa): country of origin ------------------------------------------
    origin_raw = _raw(ctx, "origin")
    imported = decl.looks_imported(_raw(ctx, "mfg_address") or "", origin_raw or "")
    r = decl.check_country_of_origin(origin_raw or "", imported_hint=imported)
    add("6(1)(aa)", r.ok, r.detail)

    # ---- Rule 6(1)(n): consumer care -------------------------------------------------
    raw = _raw(ctx, "consumer_care")
    if raw is None:
        add("6(1)(n)", False, "Consumer care details not detected.")
    else:
        r = decl.check_consumer_care(raw)
        add("6(1)(n)", r.ok, r.detail)

    # ---- Rule 6(1)(b): common / generic name ------------------------------------------
    r = decl.check_presence(_raw(ctx, "product_name"),
                            decl.FIELD_LABELS["product_name"])
    add("6(1)(b)", r.ok, r.detail)

    # ---- Rule 7: Table-I font heights ---------------------------------------------------
    if ctx.pda_cm2 is None:
        add("7", None,
            "PDA not computed (Stage 3 unavailable) — font heights not evaluated.")
    else:
        for key in _FONT_FIELDS:
            label = decl.FIELD_LABELS[key]
            label = label[0].upper() + label[1:]
            height = ctx.font_heights.get(key)
            if height is None:
                add("7", None, f"{label} font height not measured.")
                continue
            ok, required = font_height_ok(
                ctx.pda_cm2, height, ctx.blown_or_molded, FONT_TOL_MM)
            add("7", ok,
                f"{label}: measured {height:.2f} mm vs required {required:.1f} mm "
                f"({'blown/molded/embossed' if ctx.blown_or_molded else 'normal print'}, "
                f"PDA {ctx.pda_cm2:.0f} cm²).")

    # ---- Rule 7(3): character width ------------------------------------------------------
    if ctx.glyphs:
        bad = [g for g in ctx.glyphs
               if not glyph_aspect_ok(g.height_mm, g.width_mm, g.glyph)]
        if bad:
            sample = ", ".join(
                f"'{g.glyph}' {g.width_mm:.2f}x{g.height_mm:.2f} mm"
                for g in bad[:3])
            add("7(3)", False,
                f"Character width below height/3 (Rule 7(3)): {sample}.")
        else:
            add("7(3)", True,
                "All measured characters satisfy width >= height/3.")

    ctx.add_stage("s6_metrology", True, (time.perf_counter() - t0) * 1000.0)
    return ctx.checks[first:]
