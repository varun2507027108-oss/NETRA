"""NETRA dossier PDF builder (ReportLab) — the court-facing artifact.

A4 layout, Latin-1-safe text: the rupee sign maps to 'Rs.'; non-Latin-1
glyphs (e.g. Devanagari OCR text) render as '?', so decoded text is
quoted for reference only — statutory findings are ASCII by construction.

Parts:
  A  capture & device metadata (scan id, UTC, GPS, scale, PDA, exemption)
  B  statutory findings — rule / status / message + citation
  C  decoded statutory fields
  D  visual evidence — full frame with FAIL boxes + per-check crops
  E  evidence integrity chain (hashes, platform-signature policy)
  F  certificate template — section 63(4), Bharatiya Sakshya Adhiniyam,
     2023 (the provision that replaced section 65B(4), Indian Evidence Act)

Honesty note on the ~20 ms budget: the statutory record (A-C, E-F)
builds in ~20 ms; evidence image pages (D) dominate real build time.
Dossier build runs AFTER the verdict is already determined — it is off
the statutory critical path.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

try:
    import cv2
    import numpy as np          # noqa: F401  (kept for tier parity)
    HAVE_CV2 = True
except Exception:               # on-device: vision stack not installed
    HAVE_CV2 = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image as RLImage, Paragraph,
                                    SimpleDocTemplate, Spacer, Table,
                                    TableStyle)
    HAVE_REPORTLAB = True
except Exception:                                   # pragma: no cover
    HAVE_REPORTLAB = False

from .. import __version__
from ..context import CheckStatus, PipelineContext
from ..rules.citations import citation
from ..rules.declarations import FIELD_LABELS
from .crypto import sha256_hex

_CONTENT_W = 174.0            # A4 210mm - 2 x 18mm margins
_MAX_EVIDENCE_CROPS = 6
_FIT_MAX_SIDE = 1600

_REPL = {"₹": "Rs ", "\u2019": "'", "\u2018": "'", "\u201c": '"',
         "\u201d": '"', "\u2014": "-", "\u2013": "-", "\u00a0": " ",
         "\u2026": "...", "≤": "<=", "≥": ">="}


def _t(s) -> str:
    s = str(s)
    for k, v in _REPL.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _iso(dt) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC"


def _fit(img, max_side=_FIT_MAX_SIDE):
    h, w = img.shape[:2]
    s = max_side / float(max(h, w))
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)),
                         interpolation=cv2.INTER_AREA)
    return img


def _crop(frame, bbox, margin=0.15):
    h, w = frame.shape[:2]
    dx, dy = int(bbox.w * margin), int(bbox.h * margin)
    x0, y0 = max(0, bbox.x - dx), max(0, bbox.y - dy)
    x1 = min(w, bbox.x + bbox.w + dx)
    y1 = min(h, bbox.y + bbox.h + dy)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return frame[y0:y1, x0:x1]


def _rl_image(bgr, width_mm):
    if bgr is None or bgr.size == 0:
        return None
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        return None
    h, w = bgr.shape[:2]
    return RLImage(io.BytesIO(buf.tobytes()), width=width_mm * mm,
                   height=width_mm * mm * h / float(w))


_CERTIFICATE = [
    "I, ............................., son/daughter of "
    "............................., occupying the official position of "
    "............................. at ............................., do "
    "hereby certify that:",
    "1. I hold a responsible official position in relation to the "
    "operation of the mobile capture device identified in Part A of this "
    "dossier.",
    "2. The electronic record produced by that device and described in "
    "this dossier - the photographic capture bearing SHA-256 "
    "{image_sha} - was produced during the conduct of a market "
    "inspection, while the device was operating regularly and under "
    "regular control.",
    "3. The device was, to the best of my knowledge and belief, operating "
    "properly at the time of the capture; the information set out in "
    "Part A was supplied to me by that device and by the NETRA audit "
    "application.",
    "4. The integrity of the electronic record is verifiable through the "
    "SHA-256 digest recorded above, over which the attesting device "
    "affixes a hardware-backed ECDSA P-256 digital signature (see Part E).",
    "Signature of certifier: .............................   "
    "Designation: .............................",
    "Place: .............................   "
    "Date: .............................",
    "Machine attestation (NETRA {version}): this document's SHA-256 digest "
    "is recorded in the NETRA evidence ledger against scan {scan_id} and "
    "is the object of the platform digital signature, whose status at "
    "generation time was: PENDING.",
    "This certificate template is to be executed by the inspecting "
    "officer; NETRA does not sign on behalf of any person.",
]


def build_dossier_pdf(ctx: PipelineContext, source_frame=None, out_path=None):
    """-> (pdf_path_str, sha256_hex_of_pdf_bytes). Raises RuntimeError when
    reportlab is unavailable; layout errors propagate to the pipeline's
    INTERNAL envelope."""
    if not HAVE_REPORTLAB:
        raise RuntimeError("reportlab is not installed")

    if out_path is None:
        from .. import paths
        out_path = paths.dossier_dir() / f"netra_{ctx.image_id}.pdf"
    out_path = Path(out_path)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"],
                          fontSize=8.5, leading=11)
    small = ParagraphStyle("small", parent=body, fontSize=7, leading=9)
    hash_st = ParagraphStyle("hash", parent=small, wordWrap="CJK")
    cell = ParagraphStyle("cell", parent=body, fontSize=7.5, leading=9.5)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                        fontSize=12, spaceBefore=12, spaceAfter=4)

    def _p(text, style=body):
        from xml.sax.saxutils import escape
        return Paragraph(escape(_t(text)), style)

    story = []

    # ---- title + verdict banner -----------------------------------------
    verdict = ctx.verdict.value
    word = {"VIOLATION": "VIOLATION DOSSIER",
            "PASS": "COMPLIANCE RECORD"}.get(verdict, verdict)
    badge = {"VIOLATION": ("#FCE8E6", "#B3261E"),
             "PASS": ("#E6F4EA", "#1B7F3B")}.get(verdict, ("#FEF3C7", "#92400E"))
    story.append(Paragraph("NETRA - Statutory Compliance Audit",
                           styles["Title"]))
    story.append(Paragraph(
        _t("Legal Metrology (Packaged Commodities) Rules, 2011 - "
           f"automated field audit - netra-core {__version__}"), small))
    story.append(Spacer(1, 3 * mm))
    story.append(Table(
        [[Paragraph(f"<b>{_t(word)}</b>",
                    ParagraphStyle("badge", parent=body, fontSize=13,
                                   leading=16, textColor=colors.HexColor(
                                       badge[1])))]],
        colWidths=[_CONTENT_W * mm],
        style=TableStyle([("BACKGROUND", (0, 0), (-1, -1),
                           colors.HexColor(badge[0])),
                          ("BOX", (0, 0), (-1, -1), 1,
                           colors.HexColor(badge[1])),
                          ("LEFTPADDING", (0, 0), (-1, -1), 8),
                          ("TOPPADDING", (0, 0), (-1, -1), 6)])))

    # ---- Part A: capture metadata ----------------------------------------
    story.append(Paragraph("Part A - Capture, device & calibration", h2))
    meta = ctx.meta or {}
    device = meta.get("device") or {}
    gps = meta.get("gps") or {}
    device_s = ", ".join(f"{k}: {v}" for k, v in device.items()) or "not supplied"
    gps_s = (f"lat {gps.get('lat')}, lon {gps.get('lon')}"
             if gps.get("lat") is not None and gps.get("lon") is not None
             else "not supplied")
    rows = [
        ("Scan ID", ctx.image_id, cell),
        ("Verdict", verdict, cell),
        ("Captured (UTC)", _iso(ctx.captured_utc), cell),
        ("Audit duration", f"{ctx.total_ms:.1f} ms across "
                           f"{len(ctx.stages)} stages", cell),
        ("Package shape", ctx.shape_hint or "not supplied", cell),
        ("Metric scale", f"{ctx.mm_per_px:.4f} mm/px"
         if ctx.mm_per_px else "not calibrated (fiducial absent)", cell),
        ("Principal Display Area",
         f"{ctx.pda_cm2:.1f} cm2 ({ctx.pda_method})"
         if ctx.pda_cm2 else "not computed - Rule 7 reported NA", cell),
        ("Device", device_s, cell),
        ("GPS", gps_s, cell),
        ("Image SHA-256", ctx.image_sha256 or "not recorded", hash_st),
    ]
    if ctx.exemption is not None:
        rows.append(("Rule 26 exemption",
                     f"{'YES' if ctx.exemption.exempt else 'no'} - "
                     f"{ctx.exemption.note}", cell))
    story.append(Table(
        [[_p(k), _p(v, st)] for k, v, st in rows],
        colWidths=[45 * mm, (_CONTENT_W - 45) * mm],
        style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4,
                           colors.HexColor("#D0D5DD")),
                          ("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("BACKGROUND", (0, 0), (0, -1),
                           colors.HexColor("#F3F4F6"))])))

    # ---- Part B: findings --------------------------------------------------
    story.append(Paragraph("Part B - Statutory findings", h2))
    from xml.sax.saxutils import escape
    tint = {"FAIL": colors.HexColor("#FDECEA"),
            "PASS": colors.HexColor("#EAF6EE"),
            "NA": colors.HexColor("#F3F4F6")}
    fg = {"FAIL": "#B3261E", "PASS": "#1B7F3B", "NA": "#6B7280"}
    data = [["Rule", "Status", "Statutory finding"]]
    statuses = []
    for c in ctx.checks:
        statuses.append(c.status.value)
        msg = escape(_t(c.message))
        cit = escape(_t(citation(c.rule)))
        data.append([
            _p(c.rule, cell),
            Paragraph(f"<b>{c.status.value}</b>",
                      ParagraphStyle(f"st{c.status.value}", parent=cell,
                                     textColor=colors.HexColor(
                                         fg[c.status.value]))),
            Paragraph(f"{msg}<br/><font size=6.5 color=#6B7280>{cit}</font>",
                      cell)])
    cmds = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D5DD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8)]
    for i, st in enumerate(statuses, start=1):
        cmds.append(("BACKGROUND", (0, i), (-1, i), tint[st]))
    story.append(Table(data, colWidths=[20 * mm, 16 * mm,
                                        (_CONTENT_W - 36) * mm],
                       repeatRows=1, style=TableStyle(cmds)))

    # ---- Part C: decoded fields ---------------------------------------------
    story.append(Paragraph("Part C - Decoded statutory fields", h2))
    fdata = [["Field", "Value", "Raw text (OCR)", "Conf"]]
    for key, fv in ctx.fields.items():
        label = FIELD_LABELS.get(key, key)
        val = f"{fv.value} {fv.unit}".strip() if fv.value is not None else "-"
        fdata.append([_p(label, cell), _p(val, cell), _p(fv.raw, cell),
                      _p(f"{fv.conf:.2f}", cell)])
    story.append(Table(fdata, colWidths=[30 * mm, 22 * mm, 98 * mm, 24 * mm],
                       repeatRows=1,
                       style=TableStyle(cmds[:2] + [
                           ("GRID", (0, 0), (-1, -1), 0.4,
                            colors.HexColor("#D0D5DD")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")] +
                           [("BACKGROUND", (0, i), (-1, i),
                             colors.HexColor("#F9FAFB"))
                            for i in range(1, len(fdata))])))

    # ---- Part D: visual evidence ----------------------------------------------
    story.append(Paragraph("Part D - Visual evidence", h2))
    if (source_frame is not None and source_frame.size and HAVE_CV2):
        failed = [c for c in ctx.checks
                  if c.status is CheckStatus.FAIL and c.evidence is not None]
        disp = _fit(source_frame)
        if failed:
            h0, w0 = source_frame.shape[:2]
            h1, w1 = disp.shape[:2]
            sx, sy = w1 / float(w0), h1 / float(h0)
            boxed = disp.copy()
            for c in failed:
                b = c.evidence
                cv2.rectangle(boxed,
                              (int(b.x * sx), int(b.y * sy)),
                              (int((b.x + b.w) * sx), int((b.y + b.h) * sy)),
                              (0, 0, 210), max(2, int(2 * sx)))
            disp = boxed
        img = _rl_image(disp, 150.0)
        if img is not None:
            story.append(img)
            story.append(_p("Full capture; red boxes mark failing "
                            "declarations (evidence bboxes).", small))
        if failed:
            story.append(Spacer(1, 4 * mm))
            for c in failed[:_MAX_EVIDENCE_CROPS]:
                crop_img = _crop(source_frame, c.evidence)
                rl = _rl_image(crop_img, 62.0) if crop_img is not None else None
                if rl is not None:
                    story.append(rl)
                story.append(_p(f"Rule {c.rule} - {c.status.value}: "
                                f"{c.message[:140]}", small))
                story.append(Spacer(1, 3 * mm))
        else:
            story.append(_p("No failing declarations to crop.", small))
    else:
        story.append(_p("Source frame unavailable to this build "
                        "(vision stack not installed on this device).", small))

    # ---- Part E: integrity chain -----------------------------------------------
    story.append(Paragraph("Part E - Evidence integrity chain", h2))
    img_sha = ctx.image_sha256 or "not recorded"
    for line in (
        f"1. Photographic capture (submitted image): SHA-256 {img_sha}",
        f"2. This dossier document: its SHA-256 digest is recorded in the "
        f"NETRA evidence ledger (SQLite, WAL mode) against scan "
        f"{ctx.image_id} at generation time; the ledger row is the "
        f"system's authoritative record.",
        "3. Platform signature: ECDSA P-256 (Android KeyStore / iOS Secure "
        "Enclave) over the UTF-8 payload "
        f"\"NETRA-DOSSIER-v1|{ctx.image_id}|<pdf sha256 hex>\", "
        "SHA-256 digest. The platform affixes the signature after scan "
        "completion via the bridge method attach_signature; the core "
        "never holds private keys. Status at generation: PENDING.",
        "4. Hash algorithm: SHA-256 (FIPS 180-4). "
        "Signature curve: NIST P-256 (secp256r1)."):
        story.append(_p(line))

    # ---- Part F: certificate -----------------------------------------------------
    story.append(Paragraph(
        "Part F - Certificate under section 63(4), Bharatiya Sakshya "
        "Adhiniyam, 2023", h2))
    story.append(_p("[formerly section 65B(4), Indian Evidence Act, 1872]",
                    small))
    story.append(Spacer(1, 2 * mm))
    for para in _CERTIFICATE:
        story.append(_p(para.format(image_sha=img_sha,
                                    scan_id=ctx.image_id,
                                    version=__version__)))

    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 9 * mm,
                          _t(f"NETRA statutory audit dossier - "
                             f"scan {ctx.image_id}"))
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm,
                               _t(f"generated {gen} UTC - "
                                  f"page {canvas.getPageNumber()}"))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=_t(f"NETRA audit {ctx.image_id}"), author="NETRA")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    data = out_path.read_bytes()
    return str(out_path), sha256_hex(data)
