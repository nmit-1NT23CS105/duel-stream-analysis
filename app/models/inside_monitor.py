from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from math import dist
import os

import cv2

# Quiet MediaPipe / TensorFlow Lite runtime noise in the terminal.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("GLOG_minloglevel", "2")

import mediapipe as mp
import numpy as np
from ultralytics import YOLO

from app.config import Settings
from app.core.state import InsideState


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [78, 81, 13, 308, 311, 14, 82, 87, 312, 317]
NOSE_TIP = 1
LEFT_CHEEK = 234
RIGHT_CHEEK = 454
CHIN = 152
PHONE_CLASS_ID = 67


@dataclass(slots=True)
class InsideResult:
    state: InsideState
    frame: np.ndarray


class InsideMonitor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._frame_index = 0
        self._drowsy_counter = 0
        self._yawn_counter = 0
        self._distraction_counter = 0
        self._phone_counter = 0
        self._last_phone_detected = False
        self._last_phone_confidence = 0.0
        self._last_phone_box: tuple[int, int, int, int] | None = None
        self._seatbelt_counter = 0
        self._seatbelt_off_counter = 0
        self._last_seatbelt_detected = False
        self._last_seatbelt_line: tuple[int, int, int, int] | None = None
        window = max(settings.inside_smoothing_window, 1)
        self._ear_history: deque[float] = deque(maxlen=window)
        self._mar_history: deque[float] = deque(maxlen=window)
        self._head_offset_history: deque[float] = deque(maxlen=window)
        self._ear_baseline: float | None = None
        self._mar_baseline: float | None = None
        self._head_baseline: float | None = None
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._phone_detector = None
        self._phone_load_error = ""
        try:
            self._phone_detector = YOLO(settings.inside_phone_model)
        except Exception as exc:
            self._phone_load_error = str(exc)

    def reset(self) -> None:
        self._frame_index = 0
        self._drowsy_counter = 0
        self._yawn_counter = 0
        self._distraction_counter = 0
        self._phone_counter = 0
        self._last_phone_detected = False
        self._last_phone_confidence = 0.0
        self._last_phone_box = None
        self._seatbelt_counter = 0
        self._seatbelt_off_counter = 0
        self._last_seatbelt_detected = False
        self._last_seatbelt_line = None
        self._ear_history.clear()
        self._mar_history.clear()
        self._head_offset_history.clear()
        self._ear_baseline = None
        self._mar_baseline = None
        self._head_baseline = None

    @staticmethod
    def _eye_aspect_ratio(points: list[tuple[int, int]]) -> float:
        p1, p2, p3, p4, p5, p6 = points
        vertical_1 = dist(p2, p6)
        vertical_2 = dist(p3, p5)
        horizontal = max(dist(p1, p4), 1e-6)
        return (vertical_1 + vertical_2) / (2.0 * horizontal)

    @staticmethod
    def _mouth_aspect_ratio(points: list[tuple[int, int]]) -> float:
        left_corner, upper_1, top_center, right_corner, upper_2, lower_center, upper_3, lower_1, upper_4, lower_2 = points
        vertical_1 = dist(top_center, lower_center)
        vertical_2 = dist(upper_1, lower_1)
        vertical_3 = dist(upper_2, lower_2)
        vertical_4 = dist(upper_3, upper_4)
        horizontal = max(dist(left_corner, right_corner), 1e-6)
        return (vertical_1 + vertical_2 + vertical_3 + vertical_4) / (4.0 * horizontal)

    @staticmethod
    def _extract_points(landmarks, indices: list[int], width: int, height: int) -> list[tuple[int, int]]:
        return [
            (int(landmarks[idx].x * width), int(landmarks[idx].y * height))
            for idx in indices
        ]

    @staticmethod
    def _average_point(points: list[tuple[int, int]]) -> tuple[int, int]:
        count = max(len(points), 1)
        return (sum(point[0] for point in points) // count, sum(point[1] for point in points) // count)

    @staticmethod
    def _eye_width(points: list[tuple[int, int]]) -> float:
        return max(dist(points[0], points[3]), 1e-6)

    @staticmethod
    def _mean(values: deque[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _ema(current: float | None, value: float, alpha: float) -> float:
        if current is None:
            return value
        return current + alpha * (value - current)

    def _push_smoothed_metrics(self, ear: float, mar: float, head_offset: float) -> tuple[float, float, float]:
        self._ear_history.append(ear)
        self._mar_history.append(mar)
        self._head_offset_history.append(head_offset)
        return (
            self._mean(self._ear_history),
            self._mean(self._mar_history),
            self._mean(self._head_offset_history),
        )

    def _dynamic_thresholds(
        self,
        smoothed_ear: float,
        smoothed_mar: float,
        smoothed_head_offset: float,
        pose_balance: float,
        reliable_face: bool,
    ) -> tuple[float, float, float]:
        stable_face = reliable_face and smoothed_ear > self.settings.ear_threshold * 0.92
        stable_yawn = smoothed_mar < self.settings.yawn_mar_threshold * 1.05
        stable_attention = smoothed_head_offset < (
            self.settings.head_offset_threshold
            + (1.0 - pose_balance) * self.settings.pose_head_offset_bonus
        ) * 1.1

        if stable_face and stable_yawn and stable_attention:
            alpha = self.settings.baseline_update_rate
            self._ear_baseline = self._ema(self._ear_baseline, smoothed_ear, alpha)
            self._mar_baseline = self._ema(self._mar_baseline, smoothed_mar, alpha)
            self._head_baseline = self._ema(self._head_baseline, smoothed_head_offset, alpha)

        ear_baseline = self._ear_baseline if self._ear_baseline is not None else max(smoothed_ear, self.settings.ear_threshold)
        mar_baseline = self._mar_baseline if self._mar_baseline is not None else min(smoothed_mar, self.settings.yawn_mar_threshold)
        head_baseline = self._head_baseline if self._head_baseline is not None else min(smoothed_head_offset, self.settings.head_offset_threshold)

        ear_threshold = min(self.settings.ear_threshold, ear_baseline * self.settings.ear_dynamic_ratio)
        ear_threshold = max(ear_threshold, 0.12)

        mar_threshold = max(self.settings.yawn_mar_threshold, mar_baseline * self.settings.mar_dynamic_ratio)
        head_threshold = max(
            self.settings.head_offset_threshold + (1.0 - pose_balance) * self.settings.pose_head_offset_bonus,
            head_baseline + self.settings.head_dynamic_margin,
        )
        return ear_threshold, mar_threshold, head_threshold

    def _decay_counters(self, amount: int = 1) -> None:
        self._drowsy_counter = max(self._drowsy_counter - amount, 0)
        self._yawn_counter = max(self._yawn_counter - amount, 0)
        self._distraction_counter = max(self._distraction_counter - amount, 0)
        self._phone_counter = max(self._phone_counter - amount, 0)

    def _detect_phone(
        self,
        frame: np.ndarray,
        face_box: tuple[int, int, int, int],
    ) -> tuple[bool, float, tuple[int, int, int, int] | None]:
        if self._phone_detector is None:
            return False, 0.0, None

        x1, y1, x2, y2 = face_box
        height, width = frame.shape[:2]
        face_width = max(x2 - x1, 1)
        face_height = max(y2 - y1, 1)
        expanded_left = max(0, int(x1 - face_width * 0.9))
        expanded_right = min(width - 1, int(x2 + face_width * 0.9))
        expanded_top = max(0, int(y1 - face_height * 0.2))
        expanded_bottom = min(height - 1, int(y2 + face_height * 1.8))

        inference = self._phone_detector.predict(
            source=frame,
            conf=self.settings.inside_phone_confidence,
            iou=self.settings.yolo_iou,
            imgsz=self.settings.inside_phone_imgsz,
            device=self.settings.yolo_device,
            half=self.settings.yolo_half and self.settings.yolo_device != "cpu",
            verbose=False,
            classes=[PHONE_CLASS_ID],
        )
        if not inference:
            return False, 0.0, None

        boxes = inference[0].boxes
        if boxes is None or len(boxes) == 0:
            return False, 0.0, None

        confidences = boxes.conf.cpu().tolist() if boxes.conf is not None else [0.0] * len(boxes)
        xyxy_values = boxes.xyxy.int().cpu().tolist() if boxes.xyxy is not None else []

        best_confidence = 0.0
        best_box = None
        for confidence, (bx1, by1, bx2, by2) in zip(confidences, xyxy_values):
            box_area = max((bx2 - bx1), 0) * max((by2 - by1), 0)
            if box_area < self.settings.inside_phone_min_box_area:
                continue

            cx = (bx1 + bx2) // 2
            cy = (by1 + by2) // 2
            center_in_driver_zone = (
                expanded_left <= cx <= expanded_right
                and expanded_top <= cy <= expanded_bottom
            )
            if not center_in_driver_zone:
                continue

            if confidence > best_confidence:
                best_confidence = confidence
                best_box = (bx1, by1, bx2, by2)

        return best_box is not None, best_confidence, best_box

    @staticmethod
    def _evaluate_line_strap(
        gray: np.ndarray,
        p1: tuple[int, int],
        p2: tuple[int, int],
        strap_width: int = 16,
    ) -> tuple[float, float]:
        x1, y1 = p1
        x2, y2 = p2
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 35:
            return 0.0, 0.0

        nx = -dy / length
        ny = dx / length

        num_samples = int(length / 4)
        if num_samples < 6:
            return 0.0, 0.0

        center_vals: list[float] = []
        side_vals: list[float] = []
        h, w = gray.shape

        for i in range(num_samples):
            t = i / max(num_samples - 1, 1)
            cx = int(x1 + t * dx)
            cy = int(y1 + t * dy)

            lx = int(cx + nx * strap_width)
            ly = int(cy + ny * strap_width)
            rx = int(cx - nx * strap_width)
            ry = int(cy - ny * strap_width)

            if 0 <= cy < h and 0 <= cx < w and 0 <= ly < h and 0 <= lx < w and 0 <= ry < h and 0 <= rx < w:
                c = float(gray[cy, cx])
                s = (float(gray[ly, lx]) + float(gray[ry, rx])) / 2.0
                center_vals.append(c)
                side_vals.append(s)

        if len(center_vals) < 6:
            return 0.0, 0.0

        contrast = float(np.mean(side_vals) - np.mean(center_vals))
        contrast_ratio = float(np.mean([abs(s - c) >= 12.0 for c, s in zip(center_vals, side_vals)]))
        return contrast, contrast_ratio

    def _detect_seatbelt(
        self,
        frame: np.ndarray,
        face_box: tuple[int, int, int, int],
        chin_y: int | None = None,
    ) -> tuple[bool, str, tuple[int, int, int, int] | None, tuple[int, int, int, int]]:
        if not self.settings.seatbelt_detection_enabled:
            return False, "Disabled", None, (0, 0, 0, 0)

        x1, y1, x2, y2 = face_box
        height, width = frame.shape[:2]
        face_width = max(x2 - x1, 1)
        face_height = max(y2 - y1, 1)
        face_center_x = (x1 + x2) // 2
        effective_chin_y = chin_y if chin_y is not None else y2

        torso_top = min(effective_chin_y + int(face_height * 0.15), height - 1)
        torso_bottom = min(effective_chin_y + int(face_height * 2.3), height - 1)
        torso_left = max(0, face_center_x - int(face_width * 1.05))
        torso_right = min(width - 1, face_center_x + int(face_width * 1.05))
        torso_box = (torso_left, torso_top, torso_right, torso_bottom)

        rh = torso_bottom - torso_top
        rw = torso_right - torso_left
        if rh < 50 or rw < 50:
            return False, "Unknown", None, torso_box

        torso_roi = frame[torso_top:torso_bottom, torso_left:torso_right]
        gray = cv2.cvtColor(torso_roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 7, 50, 50)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        edges = cv2.Canny(enhanced, 50, 150)

        min_len = max(int(rh * 0.35), 45)
        max_gap = max(int(rh * 0.12), 15)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=40,
            minLineLength=min_len,
            maxLineGap=max_gap,
        )

        detected_now = False
        best_line = None
        best_candidate_len = 0.0

        if lines is not None:
            candidates = []
            min_angle = max(self.settings.seatbelt_min_angle, 28.0)
            max_angle = min(self.settings.seatbelt_max_angle, 68.0)
            strap_w = max(int(face_width * 0.05), 10)

            for line in lines:
                lx1, ly1, lx2, ly2 = line[0]
                dx = lx2 - lx1
                dy = ly2 - ly1
                length = math.hypot(dx, dy)
                angle = abs(math.atan2(dy, dx) * 180.0 / math.pi)

                if min_angle <= angle <= max_angle:
                    top_y = min(ly1, ly2)
                    bot_y = max(ly1, ly2)
                    v_span = bot_y - top_y
                    if v_span >= rh * 0.28 and top_y <= rh * 0.45 and bot_y >= rh * 0.50:
                        mid_x = (lx1 + lx2) / 2.0
                        if rw * 0.15 <= mid_x <= rw * 0.85:
                            gx1, gy1 = lx1 + torso_left, ly1 + torso_top
                            gx2, gy2 = lx2 + torso_left, ly2 + torso_top
                            contrast, contrast_ratio = self._evaluate_line_strap(
                                gray, (lx1, ly1), (lx2, ly2), strap_width=strap_w
                            )
                            if contrast_ratio >= 0.40 or abs(contrast) >= 14.0:
                                candidates.append({
                                    "len": length,
                                    "slope": dy / (dx if dx != 0 else 1e-5),
                                    "contrast": contrast,
                                    "ratio": contrast_ratio,
                                    "global_line": (gx1, gy1, gx2, gy2),
                                })

            for group in ([c for c in candidates if c["slope"] > 0], [c for c in candidates if c["slope"] < 0]):
                if len(group) >= 2 or (len(group) == 1 and group[0]["len"] >= rh * 0.50):
                    detected_now = True
                    group_best = max(group, key=lambda c: c["len"])
                    best_line = group_best["global_line"]
                    break

        status = "Fastened" if detected_now else "Unfastened"
        return detected_now, status, best_line, torso_box

    def analyze(self, frame: np.ndarray) -> InsideResult:
        self._frame_index += 1
        annotated = frame.copy()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb_frame)
        height, width = annotated.shape[:2]

        if not results.multi_face_landmarks:
            self._decay_counters(amount=2)
            state = InsideState(
                available=True,
                face_detected=False,
                status="No Face",
                ear=0.0,
                mar=0.0,
                attention_score=0.0,
                phone_detected=False,
                phone_confidence=0.0,
                yawning=False,
                distracted=False,
                seatbelt_detected=False,
                seatbelt_status="Unknown",
                drowsy_frames=0,
                yawn_frames=0,
                distraction_frames=0,
                confidence_note="Face not detected",
            )
            cv2.putText(
                annotated,
                "No driver face detected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )
            return InsideResult(state=state, frame=annotated)

        face_landmarks = results.multi_face_landmarks[0].landmark
        left_eye_points = self._extract_points(face_landmarks, LEFT_EYE, width, height)
        right_eye_points = self._extract_points(face_landmarks, RIGHT_EYE, width, height)
        mouth_points = self._extract_points(face_landmarks, MOUTH, width, height)

        ear_left = self._eye_aspect_ratio(left_eye_points)
        ear_right = self._eye_aspect_ratio(right_eye_points)
        left_eye_width = self._eye_width(left_eye_points)
        right_eye_width = self._eye_width(right_eye_points)
        dominant_eye_weight = min(max(self.settings.dominant_eye_weight, 0.5), 0.9)
        if left_eye_width >= right_eye_width:
            pose_weighted_ear = ear_left * dominant_eye_weight + ear_right * (1.0 - dominant_eye_weight)
        else:
            pose_weighted_ear = ear_right * dominant_eye_weight + ear_left * (1.0 - dominant_eye_weight)
        ear = pose_weighted_ear
        mar = self._mouth_aspect_ratio(mouth_points)

        nose = (
            int(face_landmarks[NOSE_TIP].x * width),
            int(face_landmarks[NOSE_TIP].y * height),
        )
        left_cheek = (
            int(face_landmarks[LEFT_CHEEK].x * width),
            int(face_landmarks[LEFT_CHEEK].y * height),
        )
        right_cheek = (
            int(face_landmarks[RIGHT_CHEEK].x * width),
            int(face_landmarks[RIGHT_CHEEK].y * height),
        )
        face_width = max(abs(right_cheek[0] - left_cheek[0]), 1)
        face_center_x = (left_cheek[0] + right_cheek[0]) / 2.0
        head_offset = abs(nose[0] - face_center_x) / face_width
        smoothed_ear, smoothed_mar, smoothed_head_offset = self._push_smoothed_metrics(ear, mar, head_offset)

        xs = [int(pt.x * width) for pt in face_landmarks]
        ys = [int(pt.y * height) for pt in face_landmarks]
        x1, y1 = max(min(xs), 0), max(min(ys), 0)
        x2, y2 = min(max(xs), width - 1), min(max(ys), height - 1)
        chin_y = int(face_landmarks[CHIN].y * height)
        face_height = max(y2 - y1, 1)
        face_width_ratio = face_width / max(width, 1)
        face_height_ratio = face_height / max(height, 1)
        eye_symmetry = abs(ear_left - ear_right) / max(smoothed_ear, 1e-6)
        pose_balance = min(left_eye_width, right_eye_width) / max(left_eye_width, right_eye_width, 1e-6)
        moderate_pose = pose_balance >= self.settings.extreme_pose_balance_threshold
        face_quality = min(
            face_width_ratio / max(self.settings.face_min_width_ratio, 1e-6),
            face_height_ratio / max(self.settings.face_min_height_ratio, 1e-6),
            1.0,
        )
        symmetry_limit = 0.65 + max(0.0, (self.settings.pose_balance_threshold - pose_balance)) * 0.9
        reliable_face = face_quality >= 0.65 and moderate_pose and eye_symmetry <= symmetry_limit
        ear_threshold, mar_threshold, head_threshold = self._dynamic_thresholds(
            smoothed_ear,
            smoothed_mar,
            smoothed_head_offset,
            pose_balance,
            reliable_face,
        )

        relative_head_offset = max(smoothed_head_offset - (self._head_baseline or 0.0), 0.0)
        head_margin = max(head_threshold - (self._head_baseline or 0.0), 1e-6)
        attention_score = max(0.0, 1.0 - min(relative_head_offset / head_margin, 1.0))

        if not reliable_face:
            self._decay_counters(amount=2)
        elif smoothed_ear < ear_threshold:
            self._drowsy_counter += 1
        else:
            self._drowsy_counter = max(self._drowsy_counter - 2, 0)

        if reliable_face and smoothed_mar > mar_threshold:
            self._yawn_counter += 1
        else:
            self._yawn_counter = max(self._yawn_counter - 1, 0)

        if reliable_face and smoothed_head_offset > head_threshold:
            self._distraction_counter += 1
        else:
            self._distraction_counter = max(self._distraction_counter - 2, 0)

        phone_detected = False
        phone_confidence = 0.0
        phone_box = None
        if reliable_face and self._phone_detector is not None:
            if self._frame_index % max(self.settings.inside_phone_detection_interval, 1) == 0 or self._last_phone_box is None:
                phone_detected_now, phone_confidence_now, detected_box = self._detect_phone(frame, (x1, y1, x2, y2))
                self._last_phone_detected = phone_detected_now
                self._last_phone_confidence = phone_confidence_now
                self._last_phone_box = detected_box

            phone_detected = self._last_phone_detected
            phone_confidence = self._last_phone_confidence
            phone_box = self._last_phone_box

            if phone_detected:
                self._phone_counter += 1
            else:
                self._phone_counter = max(self._phone_counter - 1, 0)
        else:
            self._phone_counter = max(self._phone_counter - 2, 0)
            if not reliable_face:
                self._last_phone_box = None
                self._last_phone_detected = False
                self._last_phone_confidence = 0.0

        phone_detected = self._phone_counter >= self.settings.phone_consec_frames
        phone_confidence = phone_confidence if phone_detected else 0.0
        yawning = self._yawn_counter >= self.settings.yawn_consec_frames
        distracted = self._distraction_counter >= self.settings.distraction_consec_frames
        drowsy = self._drowsy_counter >= self.settings.drowsy_consec_frames

        seatbelt_detected = False
        seatbelt_status = "Unknown"
        seatbelt_line = None
        torso_box = None
        if reliable_face and self.settings.seatbelt_detection_enabled:
            sb_detected, sb_status, sb_line, sb_torso = self._detect_seatbelt(frame, (x1, y1, x2, y2), chin_y=chin_y)
            torso_box = sb_torso
            if sb_detected:
                self._seatbelt_counter += 1
                self._seatbelt_off_counter = max(self._seatbelt_off_counter - 1, 0)
                self._last_seatbelt_line = sb_line
            else:
                self._seatbelt_off_counter += 1
                self._seatbelt_counter = max(self._seatbelt_counter - 1, 0)

            if self._seatbelt_counter >= self.settings.seatbelt_consec_frames:
                self._last_seatbelt_detected = True
            elif self._seatbelt_off_counter >= self.settings.seatbelt_consec_frames:
                self._last_seatbelt_detected = False

            seatbelt_detected = self._last_seatbelt_detected
            seatbelt_status = "Fastened" if seatbelt_detected else "Unfastened"
            seatbelt_line = self._last_seatbelt_line if seatbelt_detected else None
        else:
            seatbelt_detected = False
            seatbelt_status = "Unknown"

        if not reliable_face:
            status = "Monitoring"
            color = (255, 191, 0)
            if face_quality < 0.65:
                confidence_note = "Face too small for reliable fatigue analysis"
            else:
                confidence_note = "Face angle is too extreme for stable classification"
        elif drowsy and yawning:
            status = "Fatigue Risk"
            color = (0, 0, 255)
            confidence_note = f"Low EAR {smoothed_ear:.2f} and sustained yawn {smoothed_mar:.2f}"
        elif drowsy:
            status = "Drowsy"
            color = (0, 0, 255)
            confidence_note = f"Low EAR {smoothed_ear:.2f} below adaptive threshold {ear_threshold:.2f}"
        elif phone_detected:
            status = "Phone Use"
            color = (180, 0, 255)
            confidence_note = f"Handheld phone likely visible near driver ({phone_confidence:.2f})"
        elif distracted:
            status = "Distracted"
            color = (0, 165, 255)
            confidence_note = f"Head offset {smoothed_head_offset:.2f} above stable threshold {head_threshold:.2f}"
        elif yawning:
            status = "Yawning"
            color = (0, 215, 255)
            confidence_note = f"MAR {smoothed_mar:.2f} above adaptive yawn threshold {mar_threshold:.2f}"
        else:
            status = "Awake"
            color = (0, 255, 0)
            confidence_note = "Stable face landmarks, eyes open, and attention centered"

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        if phone_box is not None and phone_detected:
            px1, py1, px2, py2 = phone_box
            cv2.rectangle(annotated, (px1, py1), (px2, py2), (180, 0, 255), 2)
            cv2.putText(
                annotated,
                f"Phone {phone_confidence:.2f}",
                (px1, max(py1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (180, 0, 255),
                2,
            )

        for point in left_eye_points + right_eye_points:
            cv2.circle(annotated, point, 2, (255, 255, 0), -1)
        for point in mouth_points:
            cv2.circle(annotated, point, 2, (255, 140, 0), -1)
        cv2.circle(annotated, nose, 3, (255, 255, 255), -1)

        left_eye_center = self._average_point(left_eye_points)
        right_eye_center = self._average_point(right_eye_points)
        gaze_center = ((left_eye_center[0] + right_eye_center[0]) // 2, (left_eye_center[1] + right_eye_center[1]) // 2)
        cv2.line(annotated, gaze_center, nose, (255, 255, 255), 2)

        cv2.putText(
            annotated,
            f"Driver: {status}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            color,
            2,
        )
        cv2.putText(
            annotated,
            f"EAR: {smoothed_ear:.2f}",
            (20, 68),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"MAR: {smoothed_mar:.2f}",
            (20, 99),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Attention: {attention_score:.2f}",
            (20, 130),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Pose Balance: {pose_balance:.2f}",
            (20, 161),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Reliability: {face_quality:.2f}",
            (20, 192),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Phone: {'Yes' if phone_detected else 'No'}",
            (20, 223),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (255, 255, 255),
            2,
        )

        if reliable_face and self.settings.seatbelt_detection_enabled:
            if seatbelt_detected and seatbelt_line is not None:
                sx1, sy1, sx2, sy2 = seatbelt_line
                cv2.line(annotated, (sx1, sy1), (sx2, sy2), (0, 255, 128), 3)
                cv2.putText(
                    annotated,
                    "Seatbelt Worn",
                    (min(sx1, sx2), max(min(sy1, sy2) - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 128),
                    2,
                )
            elif not seatbelt_detected and torso_box is not None:
                tx1, ty1, tx2, ty2 = torso_box
                cv2.rectangle(annotated, (tx1, ty1), (tx2, ty2), (0, 0, 255), 2)
                cv2.putText(
                    annotated,
                    "NO SEATBELT",
                    (tx1 + 10, max(ty1 + 28, 25)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

        sb_color = (0, 255, 128) if seatbelt_detected else ((0, 0, 255) if reliable_face else (148, 163, 184))
        sb_display = "Fastened" if seatbelt_detected else ("No Seatbelt" if reliable_face else "Unknown")
        cv2.putText(
            annotated,
            f"Seatbelt: {sb_display}",
            (20, 254),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            sb_color,
            2,
        )

        state = InsideState(
            available=True,
            face_detected=True,
            status=status,
            ear=round(smoothed_ear, 3),
            mar=round(smoothed_mar, 3),
            attention_score=round(attention_score, 3),
            phone_detected=phone_detected,
            phone_confidence=round(phone_confidence, 3),
            yawning=yawning,
            distracted=distracted,
            seatbelt_detected=seatbelt_detected,
            seatbelt_status=seatbelt_status,
            drowsy_frames=self._drowsy_counter,
            yawn_frames=self._yawn_counter,
            distraction_frames=self._distraction_counter,
            confidence_note=confidence_note,
        )
        return InsideResult(state=state, frame=annotated)
