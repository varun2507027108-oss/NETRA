"""Train the s2 ROI model (spec: YOLO26n) and export the device artifact.

    python scripts\\train_yolo.py                 # train + fp16 tflite export
    ... --int8 --epochs 40

Model guard: tries the requested model (default yolo26n.pt); if the
installed ultralytics cannot fetch it, falls back to yolo11n.pt with a
warning — same lane, same export path.

Artifacts:
    core/models/netra_roi.pt                 desktop weights (gitignored)
    core/models/netra_roi.tflite             end-to-end (NMS-free) export
    apps/mobile/assets/yolo26n_roi.tflite    device artifact

Prints val mAP and a one-shot latency self-test — the honest number to
report next to the spec's ~39 ms on-device claim (which only the device
can measure).

Field fine-tuning: drop real photos + labels into core/yolo_ds/ (same
format) and re-run — no script changes.
"""
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "yolo_ds"
MODELS = ROOT / "models"
ASSET_DST = ROOT.parent / "apps" / "mobile" / "assets" / "yolo26n_roi.tflite"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="yolo26n.pt")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--int8", action="store_true")
    a = ap.parse_args()

    from ultralytics import YOLO

    if not (DATASET / "data.yaml").exists():
        print("dataset missing — generating default corpus first")
        from make_yolo_dataset import generate
        generate(DATASET, 400, 80, 20260906)

    try:
        model = YOLO(a.model)
        print(f"training {a.model}")
    except Exception as e:
        print(f"WARNING: {a.model} unavailable ({type(e).__name__}: {e})")
        print("falling back to yolo11n.pt — same lane, same export; "
              "re-run with --model when your ultralytics ships YOLO26")
        model = YOLO("yolo11n.pt")

    model.train(data=str(DATASET / "data.yaml"), epochs=a.epochs,
                imgsz=a.imgsz, patience=20, name="netra_roi",
                exist_ok=True, verbose=True)

    # best weights — robust across ultralytics versions
    best = Path(getattr(model.trainer, "best", "") or
                Path(model.trainer.save_dir) / "weights" / "best.pt")

    MODELS.mkdir(exist_ok=True)
    shutil.copy(best, MODELS / "netra_roi.pt")
    print(f"weights -> {MODELS / 'netra_roi.pt'}")

    tflite = model.export(format="tflite", nms=True, int8=a.int8,
                          data=str(DATASET / "data.yaml"))
    tflite = Path(tflite)
    shutil.copy(tflite, MODELS / "netra_roi.tflite")
    ASSET_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(tflite, ASSET_DST)
    print(f"device artifact -> {ASSET_DST}")

    metrics = model.val(data=str(DATASET / "data.yaml"), imgsz=a.imgsz)
    print(f"val mAP50: {metrics.box.map50:.3f}  mAP50-95: {metrics.box.map:.3f}")
    probe = str(next((DATASET / "images" / "val").glob("*.jpg")))
    t0 = time.perf_counter()
    model.predict(probe, imgsz=a.imgsz, conf=0.35, verbose=False)
    ms = (time.perf_counter() - t0) * 1000
    print(f"one-shot predict (this machine, {a.imgsz}px): {ms:.0f} ms — "
          f"spec claim is ~39 ms on-device LiteRT/NPU")
    print("NOTE: synthetic-pretrained — label it as such until field photos "
          "fine-tune it (core/yolo_ds accepts real data verbatim).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
