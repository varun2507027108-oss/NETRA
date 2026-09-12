#!/usr/bin/env python
"""tools/record_yolo_golden.py — pin the LiteRT I/O contract for NetraYolo.kt.

v2 — contract established empirically:
  input : [1,3,640,640] float32 NCHW, values ALREADY divided by 255
          (the graph does NOT normalize internally)
  output: [1,9,8400] float32 native. Rows 0-3 = cx,cy,w,h NORMALIZED [0,1]
          over the 640x640 canvas; rows 4-8 = post-sigmoid class scores.
Reference = the .pt torch model fed the EXACT same tensor (never predict(),
which letterboxes rectangularly and cannot match).
"""
import argparse, base64, hashlib, json, pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
TFLITE = ROOT / "apps/mobile/android/app/assets/yolo26n_roi.tflite"
PT = ROOT / "core/models/netra_roi.pt"
CONF, IOU, SIZE = 0.25, 0.45, 640


def letterbox(im, size=SIZE, pad=114):
    h, w = im.shape[:2]
    gain = min(size / w, size / h)
    nw, nh = max(1, int(w * gain + 0.5)), max(1, int(h * gain + 0.5))
    px, py = (size - nw) // 2, (size - nh) // 2
    out = np.full((size, size, 3), pad, np.uint8)
    out[py:py + nh, px:px + nw] = np.asarray(
        Image.fromarray(im).resize((nw, nh), Image.BILINEAR))
    return out, dict(gain=gain, padX=float(px), padY=float(py))


def iou_np(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-9)


def decode(rows_px, meta):
    """rows_px: (9, 8400); boxes in letterbox PIXELS; scores post-sigmoid."""
    scores = rows_px[4:]
    if (scores < 0).any() or (scores > 1).any():
        scores = 1 / (1 + np.exp(-scores))
    cls, conf = scores.argmax(0), scores.max(0)
    keep = conf >= CONF
    boxes = np.stack([rows_px[0] - rows_px[2] / 2,
                      rows_px[1] - rows_px[3] / 2,
                      rows_px[2], rows_px[3]], 1)[keep]
    boxes[:, 0] = (boxes[:, 0] - meta["padX"]) / meta["gain"]
    boxes[:, 1] = (boxes[:, 1] - meta["padY"]) / meta["gain"]
    boxes[:, 2] /= meta["gain"]
    boxes[:, 3] /= meta["gain"]
    dets = []
    for c in np.unique(cls[keep]):
        b = boxes[cls[keep] == c]
        s = conf[keep][cls[keep] == c]
        order = s.argsort()[::-1]
        kept = []
        for i in order:
            if all(iou_np(b[i], b[j]) <= IOU for j in kept):
                kept.append(i)
        dets += [dict(label=int(c), score=float(s[i]),
                      x=float(b[i, 0]), y=float(b[i, 1]),
                      w=float(b[i, 2]), h=float(b[i, 3])) for i in kept]
    return dets


def torch_reference(x):
    """Run the .pt on the EXACT tensor we feed the tflite."""
    import torch
    from ultralytics import YOLO
    model = YOLO(str(PT)).model.cpu().eval()
    names = {int(k): v for k, v in model.names.items()}
    with torch.no_grad():
        out = model(torch.from_numpy(x))
    if isinstance(out, (tuple, list)):
        out = out[0]
    out = out.detach().cpu().numpy()
    assert out.shape == (1, 9, 8400), f"torch raw shape {out.shape}"
    return out[0], names


def tflite_raw(x):
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
    interp = Interpreter(model_path=str(TFLITE))
    interp.allocate_tensors()
    it = interp.get_input_details()[0]
    ot = interp.get_output_details()[0]
    assert list(it["shape"]) == [1, 3, SIZE, SIZE], f"input shape {it['shape']}"
    assert list(ot["shape"]) == [1, 9, 8400], f"output shape {ot['shape']}"
    interp.set_tensor(it["index"], x)
    interp.invoke()
    return interp.get_tensor(ot["index"])[0].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    img = ap.parse_args().img
    im = np.asarray(Image.open(img).convert("RGB"))
    lb, meta = letterbox(im)
    x = np.ascontiguousarray(
        lb.astype(np.float32).transpose(2, 0, 1) / np.float32(255.0))[None]

    rows_pt, names = torch_reference(x)      # boxes in px
    rows_t = tflite_raw(x)                   # boxes normalized [0,1]
    rows_t_px = rows_t.copy()
    rows_t_px[:4] *= float(SIZE)

    fid_box = float(np.abs(rows_t_px[:4] - rows_pt[:4]).max())
    fid_scr = float(np.abs(rows_t[4:] - rows_pt[4:]).max())
    print(f"export fidelity (max|diff|): boxes {fid_box:.4f} px, "
          f"scores {fid_scr:.6f}")

    dets_pt = decode(rows_pt, meta)
    dets_t = decode(rows_t_px, meta)
    if not dets_pt:
        raise RuntimeError("torch reference decodes ZERO boxes at conf 0.25 — "
                           "try a clearer, closer photo")
    print(f"torch reference: {len(dets_pt)} boxes")
    for d in dets_pt:
        print(f"    {names[d['label']]:8s} score={d['score']:.3f} "
              f"xywh=({d['x']:.0f},{d['y']:.0f},{d['w']:.0f},{d['h']:.0f})")
    print(f"tflite decode   : {len(dets_t)} boxes")
    for d in dets_t:
        print(f"    {names[d['label']]:8s} score={d['score']:.3f} "
              f"xywh=({d['x']:.0f},{d['y']:.0f},{d['w']:.0f},{d['h']:.0f})")

    # Parity gates on conf >= 0.35 boxes only, so a borderline 0.25-gate flip
    # between float backends cannot fail an otherwise-healthy export.
    strong = [d for d in dets_pt if d["score"] >= 0.35]
    if len(dets_t) > len(dets_pt) + 3:
        raise RuntimeError("tflite produces far more boxes than torch — "
                           "paste this output back")
    for d in strong:
        m = [e for e in dets_t if e["label"] == d["label"]]
        if not any(iou_np((d["x"], d["y"], d["w"], d["h"]),
                          (e["x"], e["y"], e["w"], e["h"])) >= 0.85
                   and abs(e["score"] - d["score"]) <= 0.05 for e in m):
            raise RuntimeError(f"no tflite match for torch "
                               f"{names[d['label']]}@{d['score']:.3f} — "
                               f"paste this output back")

    if len({d["label"] for d in dets_t}) < 3:
        print("WARNING: fewer than 3 classes detected — golden is valid but "
              "parity coverage is weak; consider a photo with more fields")

    payload = dict(
        image=str(img), meta=meta,
        class_labels=[names[i] for i in range(len(names))],
        graph_normalizes_input=False,
        output_box_space="normalized_0_1",
        input=dict(shape=[1, 3, SIZE, SIZE],
                   values_b64=base64.b64encode(x.tobytes()).decode(),
                   sha256=hashlib.sha256(x.tobytes()).hexdigest()),
        output=dict(shape=[1, 9, rows_t.shape[1]],
                    values_b64=base64.b64encode(
                        rows_t.astype(np.float32).tobytes()).decode(),
                    score_min=float(rows_t[4:].min()),
                    score_max=float(rows_t[4:].max())),
        export_fidelity=dict(box_px=fid_box, score=fid_scr),
        decoded=dets_t, reference=dets_pt,
        thresholds=dict(conf=CONF, iou=IOU),
    )
    out_path = ROOT / "core/fixtures/yolo/golden_v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload))
    print(f"wrote {out_path}")
    print("  classes detected:",
          sorted(set(names[d["label"]] for d in dets_t)))


if __name__ == "__main__":
    main()
