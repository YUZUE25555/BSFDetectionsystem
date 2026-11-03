import csv
from pathlib import Path

import cv2
from ultralytics import YOLO

MODEL_PATH = Path(__file__).resolve().with_name("best 11x 200epoch.pt")
model = YOLO(str(MODEL_PATH))


def _load_validation_metrics():
    metrics_path = MODEL_PATH.parent.parent / "results.csv"
    try:
        with metrics_path.open(newline="", encoding="utf-8") as metrics_file:
            rows = list(csv.DictReader(metrics_file))
        if not rows:
            return {}

        best_row = max(
            rows,
            key=lambda row: 0.1 * float(row["metrics/mAP50(B)"])
            + 0.9 * float(row["metrics/mAP50-95(B)"]),
        )
        return {
            "map50": float(best_row["metrics/mAP50(B)"]) * 100,
            "map50_95": float(best_row["metrics/mAP50-95(B)"]) * 100,
            "precision": float(best_row["metrics/precision(B)"]) * 100,
            "recall": float(best_row["metrics/recall(B)"]) * 100,
        }
    except (OSError, KeyError, ValueError):
        return {}


VALIDATION_METRICS = _load_validation_metrics()


def reset_tracker():
    """Reset persistent ByteTrack state before starting a new video stream."""
    predictor = model.predictor
    if predictor is None:
        return

    for tracker in getattr(predictor, "trackers", []):
        tracker.reset()


def detect_frame(frame, track=False):
    if track:
        results = model.track(
            frame,
            conf=0.4,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
        )
    else:
        results = model(frame, conf=0.4, verbose=False)
    r = results[0]

    stage2_count = 0
    stage3_count = 0
    stage4_count = 0
    confidences = []
    boxes_list = []

    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            conf = float(box.conf[0].cpu().numpy()) * 100
            confidences.append(conf)
            cls_id = int(box.cls[0].cpu().numpy())
            label = f"stage{cls_id + 2}"
            track_id = (
                int(box.id[0].cpu().numpy())
                if box.id is not None else None
            )
            if cls_id in (0, 1, 2):
                boxes_list.append((*xyxy, label, conf, track_id))
            if cls_id == 0:
                stage2_count += 1
            elif cls_id == 1:
                stage3_count += 1
            elif cls_id == 2:
                stage4_count += 1

    avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

    fps_val = round(float(r.speed['inference']), 1) if hasattr(r, 'speed') else 30.0
    fps_val = round(1000 / fps_val, 1) if fps_val > 0 else 30.0

    return {
        "full": stage2_count + stage3_count + stage4_count,
        "stage2": stage2_count,
        "stage3": stage3_count,
        "stage4": stage4_count,
        "confidence": avg_conf,
        "fps": fps_val,
        "boxes": boxes_list,
    }
