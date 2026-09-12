"""Optional Ultralytics YOLO ROI provider for NETRA.

Requires `ultralytics` installed (`pip install netra-core[ml]`).
This module is a development / desktop / benchmark companion to the
on-device Kotlin LiteRT implementation (NetraYolo.kt). It mirrors the
Kotlin decoder semantics exactly.

Never import this module from `netra_core` root or any statutory engine
step — the engine remains pure standard library.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from ultralytics import YOLO  # type: ignore
except ImportError:
    YOLO = None  # type: ignore


# Model classes in canonical index order (matches NetraYolo.kt + training metadata + vision_config.json)
CLASS_LABELS: Tuple[str, ...] = ("PACKAGE", "PDP", "PRICE", "BARCODE", "BOP")


class YoloRoiProvider:
    """Detects mandatory statutory declaration ROIs using a trained YOLO model.

    This is an optional helper for offline desktop pipelines, synthetic
    evaluations, and parity verification against the Kotlin on-device
    runtime.

    Usage:
        provider = YoloRoiProvider("core/models/netra_roi.pt")
        rois = provider.detect("path/to/frame.jpg", conf=0.25)
    """

    def __init__(self, model_path: Union[str, Path]):
        if YOLO is None:
            raise ImportError(
                "Ultralytics is not installed. Install with `pip install "
                "ultralytics` or `pip install netra-core[ml]` to use "
                "YoloRoiProvider."
            )
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        self._model = YOLO(str(self.model_path))

    def detect(
        self,
        source: Union[str, Path, object],
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 640,
    ) -> List[Dict[str, Union[str, float, List[float]]]]:
        """Run ROI detection on an image.

        Args:
            source: image path, numpy array, or PIL Image.
            conf: confidence threshold (default 0.25).
            iou: NMS IoU threshold (default 0.45).
            imgsz: inference image size (default 640).

        Returns:
            List of dicts: [
                {
                    "class_name": "MRP",
                    "class_id": 0,
                    "confidence": 0.942,
                    "box_xyxy": [x1, y1, x2, y2],     # absolute pixel coords
                    "box_normalized": [cx, cy, w, h],  # 0..1 relative coords
                },
                ...
            ]
        """
        results = self._model.predict(
            source=source,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            verbose=False,
        )
        if not results:
            return []

        res = results[0]
        orig_h, orig_w = res.orig_shape
        out: List[Dict[str, Union[str, float, List[float]]]] = []

        if res.boxes is None or len(res.boxes) == 0:
            return out

        for box in res.boxes:
            cls_id = int(box.cls.item())
            conf_val = float(box.conf.item())
            xyxy = [float(v) for v in box.xyxy[0].tolist()]

            x1, y1, x2, y2 = xyxy
            cx = ((x1 + x2) / 2.0) / orig_w
            cy = ((y1 + y2) / 2.0) / orig_h
            w = (x2 - x1) / orig_w
            h = (y2 - y1) / orig_h

            cls_name = (
                CLASS_LABELS[cls_id]
                if cls_id < len(CLASS_LABELS)
                else str(cls_id)
            )

            out.append({
                "class_name": cls_name,
                "class_id": cls_id,
                "confidence": round(conf_val, 4),
                "box_xyxy": [round(v, 2) for v in xyxy],
                "box_normalized": [round(v, 4) for v in (cx, cy, w, h)],
            })

        return out
