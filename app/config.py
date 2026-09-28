from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

try:
    import torch
except Exception:  # pragma: no cover - fallback if torch import fails at startup
    torch = None


load_dotenv()
workspace_ultralytics_dir = Path(os.getenv("YOLO_CONFIG_DIR", "data/ultralytics"))
workspace_ultralytics_dir.mkdir(parents=True, exist_ok=True)
os.environ["YOLO_CONFIG_DIR"] = str(workspace_ultralytics_dir.resolve())


def _parse_source(value: str) -> int | str:
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    return stripped


def _default_yolo_device() -> str:
    if torch is not None and torch.cuda.is_available():
        return "0"
    return "cpu"


def _resolve_yolo_device(value: str | None) -> str:
    candidate = (value or "auto").strip().lower()
    if candidate in {"", "auto"}:
        return _default_yolo_device()
    return value.strip()


def _profile_defaults(profile: str) -> dict[str, str]:
    normalized = profile.strip().lower()
    if normalized == "speed":
        return {
            "YOLO_MODEL": "yolov8n.pt",
            "YOLO_CONFIDENCE": "0.35",
            "YOLO_IOU": "0.45",
            "YOLO_IMGSZ": "768",
            "MIN_VEHICLE_BOX_AREA": "1200",
        }
    if normalized == "accuracy":
        return {
            "YOLO_MODEL": "yolov8s.pt",
            "YOLO_CONFIDENCE": "0.28",
            "YOLO_IOU": "0.50",
            "YOLO_IMGSZ": "1024",
            "MIN_VEHICLE_BOX_AREA": "900",
        }
    return {
        "YOLO_MODEL": "yolov8s.pt",
        "YOLO_CONFIDENCE": "0.32",
        "YOLO_IOU": "0.48",
        "YOLO_IMGSZ": "896",
        "MIN_VEHICLE_BOX_AREA": "1000",
    }


@dataclass(slots=True)
class Settings:
    outside_profile: str = os.getenv("OUTSIDE_PROFILE", "balanced")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    inside_source: int | str = _parse_source(os.getenv("INSIDE_SOURCE", "0"))
    outside_source: int | str = _parse_source(os.getenv("OUTSIDE_SOURCE", "1"))

    inside_width: int = int(os.getenv("INSIDE_WIDTH", "960"))
    inside_height: int = int(os.getenv("INSIDE_HEIGHT", "540"))
    outside_width: int = int(os.getenv("OUTSIDE_WIDTH", "960"))
    outside_height: int = int(os.getenv("OUTSIDE_HEIGHT", "540"))

    yolo_model: str = os.getenv("YOLO_MODEL", _profile_defaults(os.getenv("OUTSIDE_PROFILE", "balanced"))["YOLO_MODEL"])
    yolo_confidence: float = float(os.getenv("YOLO_CONFIDENCE", _profile_defaults(os.getenv("OUTSIDE_PROFILE", "balanced"))["YOLO_CONFIDENCE"]))
    yolo_iou: float = float(os.getenv("YOLO_IOU", _profile_defaults(os.getenv("OUTSIDE_PROFILE", "balanced"))["YOLO_IOU"]))
    yolo_imgsz: int = int(os.getenv("YOLO_IMGSZ", _profile_defaults(os.getenv("OUTSIDE_PROFILE", "balanced"))["YOLO_IMGSZ"]))
    yolo_tracker: str = os.getenv("YOLO_TRACKER", "bytetrack.yaml")
    min_vehicle_box_area: int = int(os.getenv("MIN_VEHICLE_BOX_AREA", _profile_defaults(os.getenv("OUTSIDE_PROFILE", "balanced"))["MIN_VEHICLE_BOX_AREA"]))
    yolo_device: str = _resolve_yolo_device(os.getenv("YOLO_DEVICE", "auto"))
    yolo_half: bool = os.getenv("YOLO_HALF", "true").lower() == "true"

    ear_threshold: float = float(os.getenv("EAR_THRESHOLD", "0.23"))
    drowsy_consec_frames: int = int(os.getenv("DROWSY_CONSEC_FRAMES", "15"))
    yawn_mar_threshold: float = float(os.getenv("YAWN_MAR_THRESHOLD", "0.55"))
    yawn_consec_frames: int = int(os.getenv("YAWN_CONSEC_FRAMES", "12"))
    head_offset_threshold: float = float(os.getenv("HEAD_OFFSET_THRESHOLD", "0.11"))
    distraction_consec_frames: int = int(os.getenv("DISTRACTION_CONSEC_FRAMES", "14"))
    inside_smoothing_window: int = int(os.getenv("INSIDE_SMOOTHING_WINDOW", "5"))
    face_min_width_ratio: float = float(os.getenv("FACE_MIN_WIDTH_RATIO", "0.12"))
    face_min_height_ratio: float = float(os.getenv("FACE_MIN_HEIGHT_RATIO", "0.16"))
    baseline_update_rate: float = float(os.getenv("BASELINE_UPDATE_RATE", "0.08"))
    ear_dynamic_ratio: float = float(os.getenv("EAR_DYNAMIC_RATIO", "0.8"))
    mar_dynamic_ratio: float = float(os.getenv("MAR_DYNAMIC_RATIO", "1.35"))
    head_dynamic_margin: float = float(os.getenv("HEAD_DYNAMIC_MARGIN", "0.035"))
    pose_balance_threshold: float = float(os.getenv("POSE_BALANCE_THRESHOLD", "0.62"))
    extreme_pose_balance_threshold: float = float(os.getenv("EXTREME_POSE_BALANCE_THRESHOLD", "0.42"))
    pose_head_offset_bonus: float = float(os.getenv("POSE_HEAD_OFFSET_BONUS", "0.05"))
    dominant_eye_weight: float = float(os.getenv("DOMINANT_EYE_WEIGHT", "0.72"))
    inside_phone_model: str = os.getenv("INSIDE_PHONE_MODEL", "yolov8n.pt")
    inside_phone_confidence: float = float(os.getenv("INSIDE_PHONE_CONFIDENCE", "0.22"))
    inside_phone_imgsz: int = int(os.getenv("INSIDE_PHONE_IMGSZ", "640"))
    inside_phone_detection_interval: int = int(os.getenv("INSIDE_PHONE_DETECTION_INTERVAL", "3"))
    inside_phone_min_box_area: int = int(os.getenv("INSIDE_PHONE_MIN_BOX_AREA", "320"))
    phone_consec_frames: int = int(os.getenv("PHONE_CONSEC_FRAMES", "2"))
    inside_confidence_floor: float = float(os.getenv("INSIDE_CONFIDENCE_FLOOR", "0.18"))
    outside_confidence_floor: float = float(os.getenv("OUTSIDE_CONFIDENCE_FLOOR", "0.35"))
    fusion_low_confidence_threshold: float = float(os.getenv("FUSION_LOW_CONFIDENCE_THRESHOLD", "0.45"))

    outside_smoothing_window: int = int(os.getenv("OUTSIDE_SMOOTHING_WINDOW", "5"))
    min_track_confirmations: int = int(os.getenv("MIN_TRACK_CONFIRMATIONS", "2"))
    min_close_box_area_ratio: float = float(os.getenv("MIN_CLOSE_BOX_AREA_RATIO", "0.02"))
    edge_ignore_ratio: float = float(os.getenv("EDGE_IGNORE_RATIO", "0.015"))

    risk_smoothing_window: int = int(os.getenv("RISK_SMOOTHING_WINDOW", "6"))
    critical_persistence_frames: int = int(os.getenv("CRITICAL_PERSISTENCE_FRAMES", "2"))
    high_persistence_frames: int = int(os.getenv("HIGH_PERSISTENCE_FRAMES", "2"))

    high_event_cooldown_sec: int = int(os.getenv("HIGH_EVENT_COOLDOWN_SEC", "12"))
    snapshot_dir: Path = Path(os.getenv("SNAPSHOT_DIR", "data/events"))
    db_path: Path = Path(os.getenv("DB_PATH", "data/phase1.db"))
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
    upload_max_bytes: int = int(os.getenv("UPLOAD_MAX_BYTES", str(250 * 1024 * 1024)))
    upload_validation_frames: int = int(os.getenv("UPLOAD_VALIDATION_FRAMES", "8"))
    upload_validation_min_face_ratio: float = float(os.getenv("UPLOAD_VALIDATION_MIN_FACE_RATIO", "0.35"))
    upload_validation_min_vehicle_ratio: float = float(os.getenv("UPLOAD_VALIDATION_MIN_VEHICLE_RATIO", "0.25"))


settings = Settings()
settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
