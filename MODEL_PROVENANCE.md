# MODEL_PROVENANCE — netra_roi (YOLO26n, round 1)

- Base: yolo26n.pt (Ultralytics, AGPL-3.0) · 2.5M params · 5.3 GFLOPs
- Training: tools/colab/train_netra_roi.ipynb · imgsz 640
- Data: synthetic corpus, 5 classes, order fixed by model.names:
  PACKAGE, PDP, PRICE, BARCODE, BOP
- Metrics: mAP50 0.995 · mAP50-95 0.953 · PRICE weakest 0.859
  (PRICE is an ROI hint only — never a statutory value source)
- sha256:
    netra_roi.pt     = 271AAFE0E34DCA31F3AA2CFA75D717E2C8FC808B00DA22A14C6F61E79EE9EAB5
    yolo26n_roi.tflite = A581FF30C840B3EA4962B7BC584150E9B0499D369AF42753102AF958DA6DEC42
- Export I/O — pinned empirically by tools/record_yolo_golden.py v2,
  recorded in core/fixtures/yolo/golden_v1.json:
    input : [1,3,640,640] float32 NCHW, caller divides by 255
            (no embedded normalization in the graph)
    output: [1,9,8400] float32 native — rows 0-3 cx,cy,w,h NORMALIZED [0,1]
            over the 640x640 canvas; rows 4-8 post-sigmoid class scores;
            LiteRT export has NO embedded NMS — conf-gate + NMS owned by
            NetraYolo.kt
- Export fidelity vs .pt on identical tensor: boxes 0.0152 px · scores 6e-6
  (fp32-level, effectively bit-exact)
- Golden: core/fixtures/yolo/golden_v1.json · re-run parity after ANY model
  change; golden image: core/fixtures/yolo/golden_input.png
- Device runtime: com.google.ai.edge.litert:litert:1.0.1 (official TFLite successor; same org.tensorflow.lite.Interpreter package) — pinned after the 2.13/2.14 duplicate-namespace manifest collision. On-device raw-tensor parity 1.6e-6 vs golden (NetraYoloGoldenTest, CPH2467). Warm inference 296–360 ms mean (CPU, 4 threads).

## License flag (read before distribution)
Ultralytics is AGPL-3.0; weights trained through it are arguably
AGPL-derivative, while NETRA app code is MIT. Current status: research
prototype for SIH evaluation, not distributed — flag stands. Production
path: retrain with RF-DETR (Apache-2.0) on the same corpus; the ROI
provider is swappable by design and the engine + contract are unaffected.
