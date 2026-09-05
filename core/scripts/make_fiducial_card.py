"""Generate the printable NETRA calibration card.

Inspectors hold this card flat against the package inside the camera
frame; Stage 3 recovers the metric scale from the marker (see
netra_core/stages/s3_calibration.py).

Usage:
    python scripts/make_fiducial_card.py                     # 40 mm, 300 dpi
    python scripts/make_fiducial_card.py --side-mm 50 --dpi 600 --id 3

Print at 100% scale (no fit-to-page); the printed marker side must equal
the marker_side_mm passed to Stage 3 (default 40).
"""
import argparse

import cv2
import numpy as np

from netra_core.config import ARUCO_MARKER_MM
from netra_core.vision import aruco

CARD_W_MM, CARD_H_MM = 90.0, 60.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side-mm", type=float, default=ARUCO_MARKER_MM)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--id", type=int, default=0)
    ap.add_argument("--out", default="fiducial_card.png")
    a = ap.parse_args()

    px_per_mm = a.dpi / 25.4
    side = int(round(a.side_mm * px_per_mm))
    card_w = int(round(CARD_W_MM * px_per_mm))
    card_h = int(round(CARD_H_MM * px_per_mm))

    card = np.full((card_h, card_w), 255, np.uint8)
    marker = aruco.generate_image(a.id, side)
    x, y = (card_w - side) // 2, (card_h - side) // 2
    card[y:y + side, x:x + side] = marker

    t = max(1, int(round(0.5 * px_per_mm)))          # 0.5 mm crop marks
    m = int(round(2 * px_per_mm))
    for cx, cy, dx, dy in ((m, m, 1, 1), (card_w - m, m, -1, 1),
                           (m, card_h - m, 1, -1), (card_w - m, card_h - m, -1, -1)):
        cv2.line(card, (cx, cy), (cx + dx * int(6 * px_per_mm), cy), 0, t)
        cv2.line(card, (cx, cy), (cx, cy + dy * int(6 * px_per_mm)), 0, t)

    cv2.putText(card,
                f"NETRA fiducial  id {a.id}  {a.side_mm:.0f} mm  PRINT AT 100%",
                (int(4 * px_per_mm), card_h - int(3 * px_per_mm)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, 0, 1, cv2.LINE_AA)

    cv2.imwrite(a.out, card)
    print(f"wrote {a.out}: {CARD_W_MM:.0f}x{CARD_H_MM:.0f} mm card, "
          f"{a.side_mm:.0f} mm marker, {a.dpi} dpi")


if __name__ == "__main__":
    main()
