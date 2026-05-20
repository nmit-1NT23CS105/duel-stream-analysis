from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import dist
import os

import cv2

# Quiet MediaPipe / TensorFlow Lite runtime noise in the terminal.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("GLOG_minloglevel", "2")

import mediapipe as mp
import numpy as np

from app.config import Settings
from app.core.state import InsideState


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [78, 81, 13, 308, 311, 14, 82, 87, 312, 317]
NOSE_TIP = 1
LEFT_CHEEK = 234
RIGHT_CHEEK = 454


@dataclass(slots=True)
class InsideResult:
    state: InsideState
    frame: np.ndarray


class InsideMonitor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._drowsy_counter = 0
        self._yawn_counter = 0
        self._distraction_counter = 0
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

    def reset(self) -> None:
        self._drowsy_counter = 0
        self._yawn_counter = 0
        self._distraction_counter = 0
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

    def analyze(self, frame: np.ndarray) -> InsideResult:
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
                yawning=False,
                distracted=False,
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

        yawning = self._yawn_counter >= self.settings.yawn_consec_frames
        distracted = self._distraction_counter >= self.settings.distraction_consec_frames
        drowsy = self._drowsy_counter >= self.settings.drowsy_consec_frames

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

        state = InsideState(
            available=True,
            face_detected=True,
            status=status,
            ear=round(smoothed_ear, 3),
            mar=round(smoothed_mar, 3),
            attention_score=round(attention_score, 3),
            yawning=yawning,
            distracted=distracted,
            drowsy_frames=self._drowsy_counter,
            yawn_frames=self._yawn_counter,
            distraction_frames=self._distraction_counter,
            confidence_note=confidence_note,
        )
        return InsideResult(state=state, frame=annotated)
