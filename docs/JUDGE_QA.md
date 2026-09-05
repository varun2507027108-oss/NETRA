# NETRA — anticipated judge questions (prepared, honest answers)

**Q1. How accurate is it on real packages?**
We don't claim a field number yet — we built the machinery to earn one:
a golden-report runner that photographs real packages and reports
rule-level precision/recall per fixture. The synthetic round validates
plumbing, not field accuracy. The accuracy plan is the 3-tier OCR
stack (ML Kit → IndicPhotoOCR → Bhashini fallback). And because the
core is deterministic, errors are bounded by OCR, never by logic — a
misread fails closed (RETRY with guidance, or NA), it never invents a
compliant value.

**Q2. Why not an LLM for the compliance check?**
Statutory determinism. Same image, same verdict, every time —
auditable and cross-examinable in a way a language model cannot be.
Also: 0.45 ms, no hallucinated rule citations, and it runs fully
offline in half a millisecond.

**Q3. Is the dossier actually admissible in court?**
We claim verifiability, not admissibility. The dossier carries the
certificate template under §63(4) of the Bharatiya Sakshya Adhiniyam,
2023 (the successor to §65B(4) of the Evidence Act), a SHA-256
evidence chain, and a hardware-backed ECDSA signature. The
certificate must be executed by the inspecting officer — NETRA never
signs for a person.

**Q4. Curved or crumpled packages?**
Cylinders are flattened today — arc-length unwarping composed through
the ArUco homography, so font measurement happens in true millimetre
geometry. Thin-plate-spline correction for crumpled pouches is
roadmapped, and PDA computation falls back to inspector-measured
dimensions.

**Q5. How do you measure millimetres without camera calibration?**
Planar scale from a homography is focal-length invariant — the fiducial
card's corners define the mm→px mapping without intrinsics. When
intrinsics are known, solvePnP cross-checks the scale and reports tilt.

**Q6. What if the OCR misreads a number?**
Typed-parse gating: a value attaches only if it parses to its statutory
type. A misread yields RETRY (with an inspector prompt) or NA — never a
fabricated passing value. The one lenient path — MRP without a decodable
rupee glyph — is scope-narrowed, and the statutory phrase check stays
strict, because that's the real legal trap.

**Q7. Millions of SKUs — how does this scale?**
Per-scan cost is O(1) on the device. The institutional gateway
aggregates: PostGIS heatmaps of violation density feeding inspector
route planning — exactly the spec's institutional goal. Sync is
idempotent and append-only.

**Q8. What data leaves the device?**
Raw photographs never leave the device. The sync envelope carries
decoded statutory text, hashes, and the signature — not images, not
local file paths.

**Q9. Did you verify the Table-I values against the gazette?**
The matrix is centralized in `rules/table1_fonts.py` with a standing
note to diff against G.S.R. 629(E) before final submission — a
one-line correction if any value differs. We flag it rather than
pretend it's verified.

**Q10. What's left before real deployment?**
The device round (ML Kit + IndicPhotoOCR via the Chaquopy bridge,
YOLO26n ROIs), DoCA integration credentials for live e-Daakhil
submission, and the field fixture validation that produces the
measured precision/recall number.

**Q11. Why Flutter plus Python?**
One statutory codebase. The rules layer is stdlib-only and runs
identically in pytest, in the desktop bridge, and on-device via
Chaquopy. Kotlin is a faithful JSON pipe — zero legal logic outside
Python, ever.

**Q12. A week with no network?**
The WAL-mode SQLite ledger is append-only; sync attempts are tracked
per row; a server-rejected envelope is marked failed for a human, a
gateway outage leaves rows pending. Nothing is ever deleted.

**Q13. Tampering?**
A transmitted image whose SHA-256 doesn't match is rejected before any
processing. The signature covers the dossier's hash. The ledger is
append-only, and duplicate ingest is idempotent — you can't overwrite
evidence, only add to it.
