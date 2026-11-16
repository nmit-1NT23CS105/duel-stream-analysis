from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

import cv2
import numpy as np
from ultralytics import YOLO

from app.config import Settings
from app.core.state import OutsideState


VEHICLE_CLASS_IDS = {2, 3, 5, 7}
VRU_CLASS_IDS = {0, 1}
SIGNAL_CLASS_IDS = {9, 11}
ALL_OUTSIDE_CLASS_IDS = VEHICLE_CLASS_IDS | VRU_CLASS_IDS | SIGNAL_CLASS_IDS

CLASS_NAMES = {
    0: "Pedestrian",
    1: "Cyclist",
    2: "Car",
    3: "Bike",
    5: "Bus",
    7: "Truck",
    9: "Traffic Light",
    11: "Stop Sign",
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
        self._track_area_history: dict[int, deque[float]] = {}
        window = max(settings.outside_smoothing_window, 1)
        self._vehicle_count_history: deque[int] = deque(maxlen=window)
        self._close_count_history: deque[int] = deque(maxlen=window)
        self._proximity_history: deque[float] = deque(maxlen=window)
        self._lane_offset_history: deque[float] = deque(maxlen=window)
        self._long_lane_offset_history: deque[float] = deque(maxlen=60)
        try:
            self.model = YOLO(settings.yolo_model)
        except Exception as exc:
            self.load_error = str(exc)

    def reset(self) -> None:
        self._frame_index = 0
        self._track_memory.clear()
        self._track_area_history.clear()
        self._vehicle_count_history.clear()
        self._close_count_history.clear()
        self._proximity_history.clear()
        self._lane_offset_history.clear()
        self._long_lane_offset_history.clear()

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

    def _compute_approach_rate(self, track_id: int, area: float) -> float:
        history = self._track_area_history.setdefault(track_id, deque(maxlen=5))
        history.append(area)
        if len(history) < 3:
            return 0.0
        initial = history[0]
        if initial <= 1e-5:
            return 0.0
        growth_rate = (history[-1] - initial) / initial
        return round(growth_rate, 3)

    def _detect_lanes(
        self, frame: np.ndarray
    ) -> tuple[bool, str, float, tuple | None]:
        if not self.settings.lane_detection_enabled:
            return False, "Disabled", 0.0, None

        height, width = frame.shape[:2]
        roi_vertices = np.array(
            [
                [
                    (int(width * 0.08), height),
                    (int(width * 0.40), int(height * 0.58)),
                    (int(width * 0.60), int(height * 0.58)),
                    (int(width * 0.92), height),
                ]
            ],
            dtype=np.int32,
        )

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blur = cv2.GaussianBlur(enhanced, (5, 5), 0)
        edges = cv2.Canny(blur, 45, 135)

        mask = np.zeros_like(edges)
        cv2.fillPoly(mask, roi_vertices, 255)
        masked_edges = cv2.bitwise_and(edges, mask)

        lines = cv2.HoughLinesP(
            masked_edges,
            1,
            np.pi / 180,
            threshold=32,
            minLineLength=35,
            maxLineGap=25,
        )

        if lines is None:
            return False, "Unmarked", 0.0, None

        left_pts = []
        right_pts = []
        mid_x = width // 2

        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            dy = y2 - y1
            if abs(dx) < 1e-5:
                continue
            slope = dy / dx
            angle = math.atan2(abs(dy), abs(dx)) * 180.0 / math.pi
            if 22 <= angle <= 82:
                if slope > 0 and (x1 < mid_x or x2 < mid_x + 50):
                    left_pts.extend([(x1, y1), (x2, y2)])
                elif slope < 0 and (x1 > mid_x - 50 or x2 > mid_x):
                    right_pts.extend([(x1, y1), (x2, y2)])

        if not left_pts and not right_pts:
            return False, "Unmarked", 0.0, None

        y_bottom = height
        y_top = int(height * 0.65)

        if len(left_pts) >= 2:
            vx, vy, x0, y0 = cv2.fitLine(np.array(left_pts), cv2.DIST_L2, 0, 0.01, 0.01)
            vx, vy, x0, y0 = float(vx), float(vy), float(x0), float(y0)
            if abs(vy) > 1e-5:
                left_bottom_x = int(x0 + (y_bottom - y0) * (vx / vy))
                left_top_x = int(x0 + (y_top - y0) * (vx / vy))
            else:
                left_bottom_x = int(width * 0.20)
                left_top_x = int(width * 0.42)
        else:
            left_bottom_x = int(width * 0.20)
            left_top_x = int(width * 0.42)

        if len(right_pts) >= 2:
            vx, vy, x0, y0 = cv2.fitLine(np.array(right_pts), cv2.DIST_L2, 0, 0.01, 0.01)
            vx, vy, x0, y0 = float(vx), float(vy), float(x0), float(y0)
            if abs(vy) > 1e-5:
                right_bottom_x = int(x0 + (y_bottom - y0) * (vx / vy))
                right_top_x = int(x0 + (y_top - y0) * (vx / vy))
            else:
                right_bottom_x = int(width * 0.80)
                right_top_x = int(width * 0.58)
        else:
            right_bottom_x = int(width * 0.80)
            right_top_x = int(width * 0.58)

        corridor = (
            (left_bottom_x, y_bottom),
            (left_top_x, y_top),
            (right_top_x, y_top),
            (right_bottom_x, y_bottom),
        )

        lane_center_x = (left_bottom_x + right_bottom_x) / 2.0
        ego_center_x = width / 2.0
        deviation = (ego_center_x - lane_center_x) / width
        thresh = self.settings.lane_drift_threshold

        has_both = len(left_pts) >= 2 and len(right_pts) >= 2
        if has_both:
            if deviation > thresh:
                status = "Drifting Right"
            elif deviation < -thresh:
                status = "Drifting Left"
            else:
                status = "Centered"
        else:
            status = "Tracking"

        return True, status, round(deviation, 3), corridor

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
                pedestrian_count=0,
                cyclist_count=0,
                vru_risk=False,
                tracked_count=0,
                close_vehicle=False,
                ttc_seconds=0.0,
                ttc_warning=False,
                traffic_signal="NONE",
                stop_sign_detected=False,
                weather_condition="Clear Daylight",
                traffic_level="Unknown",
                confidence_note=note,
            )
            return OutsideResult(state=state, frame=annotated)

        classes_to_track = list(ALL_OUTSIDE_CLASS_IDS) if (self.settings.vru_detection_enabled or self.settings.traffic_signals_enabled) else list(VEHICLE_CLASS_IDS)
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
            classes=classes_to_track,
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
        rapid_approach = False
        max_approach_rate = 0.0
        class_counts: dict[str, int] = {}
        proximity_score = 0.0
        pedestrian_count = 0
        cyclist_count = 0
        vru_risk = False
        traffic_signal = "NONE"
        stop_sign_detected = False
        min_ttc = 99.0

        # Environmental Visibility & Weather Assessment
        gray_env = cv2.cvtColor(annotated, cv2.COLOR_BGR2GRAY)
        mean_lum = float(np.mean(gray_env))
        lap_var = float(cv2.Laplacian(gray_env, cv2.CV_64F).var())
        if mean_lum < 42.0:
            weather_condition = "Night / Low Light"
        elif lap_var < 52.0 and mean_lum < 160.0:
            weather_condition = "Fog / Low Visibility"
        elif mean_lum > 225.0:
            weather_condition = "High Sun Glare"
        else:
            weather_condition = "Clear Daylight"

        edge_margin_x = int(width * self.settings.edge_ignore_ratio)
        edge_margin_y = int(height * self.settings.edge_ignore_ratio)
        frame_area = max(width * height, 1)

        if boxes is not None and len(boxes) > 0:
            track_ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
            class_ids = boxes.cls.int().cpu().tolist() if boxes.cls is not None else [0] * len(boxes)
            confidences = boxes.conf.cpu().tolist() if boxes.conf is not None else [0.0] * len(boxes)
            xyxy_values = boxes.xyxy.int().cpu().tolist() if boxes.xyxy is not None else []

            for track_id, cls_id, confidence, (x1, y1, x2, y2) in zip(track_ids, class_ids, confidences, xyxy_values):
                box_area = max((x2 - x1), 0) * max((y2 - y1), 0)
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                # Vulnerable Road Users (Pedestrians & Cyclists)
                if cls_id in VRU_CLASS_IDS:
                    if box_area < 350:
                        continue
                    if cls_id == 0:
                        pedestrian_count += 1
                        label = "Pedestrian"
                    else:
                        cyclist_count += 1
                        label = "Cyclist"
                    in_close_corridor = (close_zone[0] - 50 <= cx <= close_zone[2] + 50) and (cy >= int(height * 0.40))
                    if in_close_corridor:
                        vru_risk = True
                    vru_color = (0, 0, 255) if in_close_corridor else (255, 0, 255)
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), vru_color, 2)
                    cv2.putText(annotated, f"{label} {confidence:.2f}", (x1, max(y1 - 6, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, vru_color, 2)
                    continue

                # Traffic Signals & Stop Signs
                if cls_id in SIGNAL_CLASS_IDS:
                    if cls_id == 9:
                        tx1, ty1, tx2, ty2 = max(x1, 0), max(y1, 0), min(x2, width), min(y2, height)
                        light_crop = frame[ty1:ty2, tx1:tx2]
                        if light_crop.size > 20:
                            hsv = cv2.cvtColor(light_crop, cv2.COLOR_BGR2HSV)
                            mask_r = ((hsv[:,:,0] < 10) | (hsv[:,:,0] > 165)) & (hsv[:,:,1] > 70) & (hsv[:,:,2] > 80)
                            mask_g = (hsv[:,:,0] >= 35) & (hsv[:,:,0] <= 85) & (hsv[:,:,1] > 70) & (hsv[:,:,2] > 80)
                            mask_y = (hsv[:,:,0] >= 15) & (hsv[:,:,0] <= 32) & (hsv[:,:,1] > 70) & (hsv[:,:,2] > 80)
                            r_cnt, g_cnt, y_cnt = int(np.sum(mask_r)), int(np.sum(mask_g)), int(np.sum(mask_y))
                            if r_cnt > 12 and r_cnt >= g_cnt:
                                traffic_signal = "RED"
                            elif g_cnt > 12 and g_cnt >= r_cnt:
                                traffic_signal = "GREEN"
                            elif y_cnt > 10:
                                traffic_signal = "YELLOW"
                        sig_color = (0, 0, 255) if traffic_signal == "RED" else ((0, 255, 0) if traffic_signal == "GREEN" else (0, 255, 255))
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), sig_color, 2)
                        cv2.putText(annotated, f"Signal: {traffic_signal}", (x1, max(y1 - 6, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, sig_color, 2)
                    elif cls_id == 11:
                        stop_sign_detected = True
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(annotated, "STOP SIGN", (x1, max(y1 - 6, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                    continue

                if cls_id not in VEHICLE_CLASS_IDS:
                    continue

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
                in_zone = close_zone[0] <= cx <= close_zone[2] and close_zone[1] <= cy <= close_zone[3]
                label = CLASS_NAMES.get(cls_id, "Vehicle")
                class_counts[label] = class_counts.get(label, 0) + 1
                proximity_score = max(proximity_score, area_ratio)
                bottom_anchor = y2 >= int(height * 0.62)
                close_candidate = in_zone and (
                    area_ratio >= self.settings.min_close_box_area_ratio or bottom_anchor
                )
                if close_candidate:
                    close_vehicle = True
                    close_vehicle_count += 1

                approach_rate = 0.0
                if track_id is not None:
                    approach_rate = self._compute_approach_rate(track_id, area_ratio)

                is_rapid_approach = in_zone and approach_rate >= self.settings.rapid_approach_threshold
                if is_rapid_approach:
                    rapid_approach = True
                    max_approach_rate = max(max_approach_rate, approach_rate)

                if in_zone and approach_rate > 0.04:
                    calculated_ttc = round(1.0 / max(approach_rate, 0.01) * 0.35, 1)
                    if calculated_ttc < min_ttc:
                        min_ttc = calculated_ttc

                color = (0, 0, 255) if (close_candidate or is_rapid_approach) else (0, 200, 0)
                id_text = f"#{track_id}" if track_id is not None else "#?"
                if is_rapid_approach:
                    caption = f"{label} {id_text} CLOSING FAST (+{int(approach_rate*100)}%)"
                else:
                    caption = f"{label} {id_text} {confidence:.2f}"

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3 if is_rapid_approach else 2)
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

        # Lane Detection
        lane_detected, lane_status, lane_offset, corridor = self._detect_lanes(frame)
        self._lane_offset_history.append(lane_offset)
        self._long_lane_offset_history.append(lane_offset)
        stable_lane_offset = self._mean_float(self._lane_offset_history)

        sudden_lane_change = False
        weaving_detected = False
        if len(self._long_lane_offset_history) >= 12:
            recent_delta = abs(self._long_lane_offset_history[-1] - self._long_lane_offset_history[-10])
            if recent_delta >= 0.12:
                sudden_lane_change = True

            offsets = list(self._long_lane_offset_history)
            diffs = [offsets[i] - offsets[i - 1] for i in range(1, len(offsets))]
            sign_reversals = sum(1 for i in range(1, len(diffs)) if (diffs[i] * diffs[i - 1] < -1e-4 and abs(diffs[i]) > 0.015))
            if sign_reversals >= 3 and max(abs(x) for x in offsets[-25:]) > 0.05:
                weaving_detected = True

        if weaving_detected:
            lane_status = "Repeated Weaving"
        elif sudden_lane_change:
            lane_status = "Sudden Lane Change"

        # Relative and estimated speed calculations (P2-FR07 / Overspeed)
        speed_delta_kph = int(round(max_approach_rate * 60.0))
        if rapid_approach:
            relative_speed_estimate = f"+{speed_delta_kph} km/h closing (vision-based estimate)"
        elif max_approach_rate > 0.05:
            relative_speed_estimate = f"+{speed_delta_kph} km/h (vision-based estimate)"
        else:
            relative_speed_estimate = "Stable (vision-based estimate)"
        speed_estimate_label = "Vision-based estimate"

        base_speed = 50.0 if vehicle_count_now > 0 else 0.0
        estimated_speed_kmh = round(base_speed + speed_delta_kph, 1) if vehicle_count_now > 0 else 0.0
        speed_limit_kmh = self.settings.speed_limit_kmh
        overspeed_detected = bool(vehicle_count_now > 0 and estimated_speed_kmh > speed_limit_kmh and rapid_approach)
        speed_status = "AVAILABLE" if vehicle_count_now > 0 else "STANDBY"

        # Compute Time-To-Collision (TTC)
        if min_ttc < 99.0:
            ttc_seconds = min_ttc
            ttc_warning = ttc_seconds <= self.settings.ttc_alert_threshold
        elif rapid_approach:
            ttc_seconds = 1.8
            ttc_warning = True
        else:
            ttc_seconds = 0.0
            ttc_warning = False

        # Aggressive driving risk calculation (P2-FR08)
        agg_score = 0
        if weaving_detected:
            agg_score += 35
        if sudden_lane_change:
            agg_score += 30
        if close_vehicle:
            agg_score += 25
        if rapid_approach:
            agg_score += 25
        aggressive_driving_score = min(agg_score, 100)
        aggressive_driving_detected = aggressive_driving_score >= 50

        if corridor is not None:
            overlay = annotated.copy()
            lane_poly = np.array([corridor[0], corridor[1], corridor[2], corridor[3]], dtype=np.int32)
            corridor_color = (0, 200, 100) if lane_status == "Centered" else (0, 80, 255)
            cv2.fillPoly(overlay, [lane_poly], corridor_color)
            cv2.addWeighted(overlay, 0.25, annotated, 0.75, 0, annotated)
            border_color = (0, 255, 128) if lane_status == "Centered" else (0, 120, 255)
            cv2.line(annotated, corridor[0], corridor[1], border_color, 2)
            cv2.line(annotated, corridor[3], corridor[2], border_color, 2)

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
            f"Traffic: {traffic_level}",
            (20, 68),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Close Vehicles: {stable_close_count}",
            (20, 101),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
        )
        lane_color = (0, 255, 128) if lane_status == "Centered" else ((0, 120, 255) if ("Drift" in lane_status or "Weaving" in lane_status or "Sudden" in lane_status) else (200, 200, 200))
        cv2.putText(
            annotated,
            f"Lane: {lane_status} ({stable_lane_offset:+.2f})",
            (20, 134),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            lane_color,
            2,
        )
        approach_color = (0, 0, 255) if rapid_approach else (255, 255, 255)
        cv2.putText(
            annotated,
            f"Approach: {'RAPID (+' + str(int(max_approach_rate*100)) + '%)' if rapid_approach else 'Stable'}",
            (20, 167),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.70,
            approach_color,
            2,
        )
        cv2.putText(
            annotated,
            f"Rel Speed: {relative_speed_estimate}",
            (20, 198),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (0, 165, 255) if rapid_approach else (255, 255, 255),
            2,
        )
        agg_color = (0, 0, 255) if aggressive_driving_detected else ((0, 200, 255) if aggressive_driving_score > 0 else (255, 255, 255))
        cv2.putText(
            annotated,
            f"Aggressive Risk: {aggressive_driving_score}/100",
            (20, 229),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            agg_color,
            2,
        )

        if vru_risk:
            cv2.putText(
                annotated,
                "VRU ALERT: Pedestrian/Bike Ahead",
                (20, 260),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2,
            )
        if ttc_warning and ttc_seconds > 0:
            cv2.putText(
                annotated,
                f"TTC WARNING: {ttc_seconds:.1f}s",
                (20, 290),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2,
            )
        cv2.putText(
            annotated,
            f"Env: {weather_condition}",
            (20, 320),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2,
        )

        state = OutsideState(
            available=True,
            vehicle_count=vehicle_count_now,
            pedestrian_count=pedestrian_count,
            cyclist_count=cyclist_count,
            vru_risk=vru_risk,
            tracked_count=vehicle_count_now,
            close_vehicle=close_vehicle,
            close_vehicle_count=stable_close_count,
            proximity_score=round(stable_proximity, 3),
            class_counts=class_counts,
            traffic_level=traffic_level,
            lane_detected=lane_detected,
            lane_status=lane_status,
            lane_offset=round(stable_lane_offset, 3),
            sudden_lane_change=sudden_lane_change,
            weaving_detected=weaving_detected,
            rapid_approach=rapid_approach,
            approach_rate=round(max_approach_rate, 3),
            ttc_seconds=round(ttc_seconds, 1),
            ttc_warning=ttc_warning,
            relative_speed_estimate=relative_speed_estimate,
            speed_estimate_label=speed_estimate_label,
            estimated_speed_kmh=estimated_speed_kmh,
            speed_limit_kmh=speed_limit_kmh,
            overspeed_detected=overspeed_detected,
            speed_status=speed_status,
            traffic_signal=traffic_signal,
            stop_sign_detected=stop_sign_detected,
            weather_condition=weather_condition,
            aggressive_driving_score=aggressive_driving_score,
            aggressive_driving_detected=aggressive_driving_detected,
            confidence_note=f"{class_summary} | Lane {lane_status} | {weather_condition}",
        )
        return OutsideResult(state=state, frame=annotated)
