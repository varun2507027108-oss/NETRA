"""Stage 7 — verifiable violation dossier generation.

Builds the court-facing PDF (dossier/pdf_builder), computes its SHA-256,
sets ctx.dossier_* for the bridge result, and arms the platform-signing
handshake (contract section 8): Flutter/Kotlin signs
dossier.crypto.sign_payload(...) with hardware-backed ECDSA P-256 and
returns the signature via bridge attach_signature, which flips the
ledger row to signed. The evidence LEDGER write itself happens in the
pipeline after serialization (stage = document, pipeline = ledger).

Gating: VIOLATION always generates; PASS only with options.dossier_on_pass;
RETRY never (no record to file). Missing reportlab degrades gracefully —
a document-rendering dependency must never fail a statutory scan.
PDF build failures (disk, layout) DO fail the stage: an unsigned, broken
dossier is not a deliverable, and the scan surfaces as RETRY with the
reason recorded.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from ..context import PipelineContext, Verdict
from ..dossier import pdf_builder


@dataclass(frozen=True)
class DossierReport:
    ok: bool
    generated: bool
    reason: str
    pdf_path: Optional[str] = None
    sha256: Optional[str] = None


def run(ctx: PipelineContext, source_frame=None,
        options: Optional[dict] = None) -> DossierReport:
    t0 = time.perf_counter()
    opts = dict(options or {})
    verdict = ctx.verdict

    if verdict is Verdict.RETRY:
        report = DossierReport(True, False,
                               "verdict RETRY - no dossier (rescan first)")
    elif verdict is Verdict.PASS and not opts.get("dossier_on_pass"):
        report = DossierReport(True, False,
                               "verdict PASS - dossier only with "
                               "options.dossier_on_pass")
    elif not pdf_builder.HAVE_REPORTLAB:
        report = DossierReport(True, False,
                               "reportlab not installed "
                               "(pip install netra-core)")
    else:
        try:
            path, sha = pdf_builder.build_dossier_pdf(ctx, source_frame)
            ctx.dossier_sha256 = sha
            ctx.dossier_path = path
            report = DossierReport(True, True,
                                   f"dossier {path} (sha256 recorded, "
                                   f"signature pending)", path, sha)
        except Exception as e:
            report = DossierReport(False, False,
                                    f"dossier generation failed: "
                                    f"{type(e).__name__}: {e}")

    ctx.add_stage("s7_dossier", report.ok, (time.perf_counter() - t0) * 1000.0)
    return report
