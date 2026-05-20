from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np
from ultralytics import YOLO

from app.config import Settings
from app.core.state import OutsideState


VEHICLE_CLASS_IDS = {2, 3, 5, 7}
VEHICLE_CLASS_NAMES = {
    2: "Car",
    3: "Bike",
    5: "Bus",
    7: "Truck",
}


@dataclass(slots=True)
class OutsideResult:
    state: OutsideState
    frame: np.ndarray


class OutsideMonitor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = None
        self.load_error = ""
        self._frame_index = 0
        self._track_memory: dict[int, dict[str, int]] = {}
        window = max(settings.outside_smoothing_window, 1)
        self._vehicle_count_history: deque[int] = deque(maxlen=window)
        self._close_count_history: deque[int] = deque(maxlen=window)
        self._proximity_history: deque[float] = deque(maxlen=window)
        try:
            self.model = YOLO(settings.yolo_model)
        except Exception as exc:
            self.load_error = str(exc)

    def reset(self) -> None:
        self._frame_index = 0
        self._track_memory.clear()
        self._vehicle_count_history.clear()
        self._close_count_history.clear()
        self._proximity_history.clear()

    @staticmethod
    def _mean_int(values: deque[int]) -> int:
        if not values:
            return 0
        return int(round(sum(values) / len(values)))

    @staticmethod
    def _mean_float(values: deque[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _update_track_streak(self, track_id: int) -> int:
        entry = self._track_memory.get(track_id, {"streak": 0, "last_seen": -99})
        if entry["last_seen"] == self._frame_index - 1:
            entry["streak"] += 1
        else:
            entry["streak"] = 1
        entry["last_seen"] = self._frame_index
        self._track_memory[track_id] = entry
        return entry["streak"]

    def _prune_tracks(self) -> None:
        stale_ids = [
            track_id
            for track_id, entry in self._track_memory.items()
            if self._frame_index - entry["last_seen"] > 10
        ]
        for track_id in stale_ids:
            self._track_memory.pop(track_id, None)

    def analyze(self, frame: np.ndarray) -> OutsideResult:
        annotated = frame.copy()
        height, width = annotated.shape[:2]
        self._frame_index += 1

        if self.model is None:
            cv2.putText(
                annotated,
                "YOLO weights unavailable",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 140, 255),
                2,
            )
            note = "Vehicle detector not ready"
            if self.load_error:
                note = f"Vehicle detector load failed: {self.load_error[:80]}"
            state = OutsideState(
                available=False,
                vehicle_count=0,
                tracked_count=0,
                close_vehicle=False,
                traffic_level="Unknown",
                confidence_note=note,
            )
            return OutsideResult(state=state, frame=annotated)

        inference = self.model.track(
            source=annotated,
            conf=self.settings.yolo_confidence,
            iou=self.settings.yolo_iou,
            imgsz=self.settings.yolo_imgsz,
            tracker=self.settings.yolo_tracker,
            persist=True,
            device=self.settings.yolo_device,
            half=self.settings.yolo_half and self.settings.yolo_device != "cpu",
            verbose=False,
            classes=list(VEHICLE_CLASS_IDS),
        )

        result = inference[0]
        boxes = result.boxes

        close_zone = (
            int(width * 0.30),
            int(height * 0.42),
            int(width * 0.70),
            int(height * 0.98),
        )
        cv2.rectangle(annotated, (close_zone[0], close_zone[1]), (close_zone[2], close_zone[3]), (255, 215, 0), 2)
        cv2.putText(
            annotated,
            "Front Risk Zone",
            (close_zone[0], max(close_zone[1] - 12, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 215, 0),
            2,
        )

        active_ids: set[int] = set()
        close_vehicle = False
        close_vehicle_count = 0
        class_counts: dict[str, int] = {}
        proximity_score = 0.0
        edge_margin_x = int(width * self.settings.edge_ignore_ratio)
        edge_margin_y = int(height * self.settings.edge_ignore_ratio)
        frame_area = max(width * height, 1)

        if boxes is not None and len(boxes) > 0:
            track_ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
            class_ids = boxes.cls.int().cpu().tolist() if boxes.cls is not None else [0] * len(boxes)
            confidences = boxes.conf.cpu().tolist() if boxes.conf is not None else [0.0] * len(boxes)
            xyxy_values = boxes.xyxy.int().cpu().tolist() if boxes.xyxy is not None else []

            for track_id, cls_id, confidence, (x1, y1, x2, y2) in zip(track_ids, class_ids, confidences, xyxy_values):
                if cls_id not in VEHICLE_CLASS_IDS:
                    continue

                box_area = max((x2 - x1), 0) * max((y2 - y1), 0)
                if box_area < self.settings.min_vehicle_box_area:
                    continue

                area_ratio = box_area / frame_area
                touches_edge = (
                    x1 <= edge_margin_x
                    or x2 >= width - edge_margin_x
                    or y1 <= edge_margin_y
                )
                if touches_edge and area_ratio < 0.03 and confidence < self.settings.yolo_confidence + 0.12:
                    continue

                streak = 1
                if track_id is not None:
                    streak = self._update_track_streak(track_id)

                confirmed = (
                    streak >= self.settings.min_track_confirmations
                    or confidence >= self.settings.yolo_confidence + 0.16
                    or area_ratio >= 0.045
                )
                if not confirmed:
                    continue

                active_ids.add(track_id if track_id is not None else len(active_ids) + 1)
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                in_zone = close_zone[0] <= cx <= close_zone[2] and close_zone[1] <= cy <= close_zone[3]
                label = VEHICLE_CLASS_NAMES.get(cls_id, "Vehicle")
                class_counts[label] = class_counts.get(label, 0) + 1
                proximity_score = max(proximity_score, area_ratio)
                bottom_anchor = y2 >= int(height * 0.62)
                close_candidate = in_zone and (
                    area_ratio >= self.settings.min_close_box_area_ratio or bottom_anchor
                )
                if close_candidate:
                    close_vehicle = True
                    close_vehicle_count += 1

                color = (0, 0, 255) if close_candidate else (0, 200, 0)
                id_text = f"#{track_id}" if track_id is not None else "#?"
                caption = f"{label} {id_text} {confidence:.2f}"

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.circle(annotated, (cx, cy), 4, color, -1)
                cv2.putText(
                    annotated,
                    caption,
                    (x1, max(y1 - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.58,
                    color,
                    2,
                )

        self._prune_tracks()
        vehicle_count_now = len(active_ids)
        self._vehicle_count_history.append(vehicle_count_now)
        self._close_count_history.append(close_vehicle_count)
        self._proximity_history.append(proximity_score)

        stable_vehicle_count = self._mean_int(self._vehicle_count_history)
        stable_close_count = self._mean_int(self._close_count_history)
        stable_proximity = self._mean_float(self._proximity_history)
        close_vehicle = stable_close_count > 0

        if stable_vehicle_count >= 8:
            traffic_level = "High"
        elif stable_vehicle_count >= 4:
            traffic_level = "Medium"
        elif stable_vehicle_count > 0:
            traffic_level = "Low"
        else:
            traffic_level = "Clear"

        class_summary = " | ".join(
            f"{label}:{count}" for label, count in sorted(class_counts.items(), key=lambda item: item[0])
        ) or "No vehicles"

        cv2.putText(
            annotated,
            f"Vehicles Now: {vehicle_count_now}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Tracked IDs: {vehicle_count_now}",
            (20, 68),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Traffic: {traffic_level}",
            (20, 101),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Close Vehicles: {stable_close_count}",
            (20, 134),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            class_summary[:75],
            (20, 167),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
        )

        state = OutsideState(
            available=True,
            vehicle_count=vehicle_count_now,
            tracked_count=vehicle_count_now,
            close_vehicle=close_vehicle,
            close_vehicle_count=stable_close_count,
            proximity_score=round(stable_proximity, 3),
            class_counts=class_counts,
            traffic_level=traffic_level,
            confidence_note=class_summary,
        )
        return OutsideResult(state=state, frame=annotated)
