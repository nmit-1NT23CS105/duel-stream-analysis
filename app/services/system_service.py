from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Generator

import cv2
import numpy as np

from app.config import Settings
from app.core.state import InputState, InsideState, OutsideState, SystemState
from app.fusion.risk_engine import RiskEngine
from app.models.inside_monitor import InsideMonitor
from app.models.outside_monitor import OutsideMonitor, VEHICLE_CLASS_IDS
from app.storage.event_store import EventStore

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}


class DualStreamService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state = SystemState(
            input=InputState(
                mode="live",
                inside_source=str(settings.inside_source),
                outside_source=str(settings.outside_source),
                enabled=False,
            )
        )
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._inside_frame = self._placeholder_frame("Inside stream starting")
        self._outside_frame = self._placeholder_frame("Outside stream starting")
        self._risk_engine = RiskEngine(settings)
        self._inside_monitor = InsideMonitor(settings)
        self._outside_monitor = OutsideMonitor(settings)
        self._event_store = EventStore(settings)
        self._threads: list[threading.Thread] = []
        self._source_versions = {"inside": 0, "outside": 0}
        self._pending_uploaded_sources = {"inside": "", "outside": ""}
        self._recorded_validation = self._empty_validation_bundle()
        self._validation_cache: dict[str, dict] = {}
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        if self.state.started:
            return
        self.state.started = True
        self._threads = [
            threading.Thread(target=self._inside_loop, name="inside-loop", daemon=True),
            threading.Thread(target=self._outside_loop, name="outside-loop", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=2.0)

    def get_state(self) -> dict:
        with self._lock:
            return self.state.to_dict()

    def get_recent_events(
        self,
        limit: int = 10,
        risk_level: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        return self._event_store.fetch_events(limit=limit, risk_level=risk_level, category=category, search=search)

    def export_events_csv(
        self,
        risk_level: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> str:
        return self._event_store.export_csv(risk_level=risk_level, category=category, search=search)

    def get_input_config(self) -> dict:
        with self._lock:
            return {
                "mode": self.state.input.mode,
                "inside_source": self.state.input.inside_source,
                "outside_source": self.state.input.outside_source,
                "enabled": self.state.input.enabled,
                "validation": self._recorded_validation,
            }

    def configure_inputs(
        self,
        mode: str,
        inside_source: str | None = None,
        outside_source: str | None = None,
    ) -> dict:
        normalized_mode = mode.lower().strip()
        if normalized_mode not in {"live", "recorded"}:
            raise ValueError("Mode must be 'live' or 'recorded'.")

        validation_bundle = self._empty_validation_bundle()
        next_inside = ""
        next_outside = ""

        if normalized_mode == "recorded":
            current_config = self.get_input_config()
            next_inside = inside_source.strip() if inside_source is not None else current_config["inside_source"]
            next_outside = outside_source.strip() if outside_source is not None else current_config["outside_source"]
            next_inside, next_outside = self._prepare_recorded_sources(next_inside, next_outside)
            validation_bundle = self._build_recorded_validation_bundle(next_inside, next_outside)

        with self._lock:
            if normalized_mode != "recorded":
                next_inside = inside_source.strip() if inside_source is not None else self.state.input.inside_source
                next_outside = outside_source.strip() if outside_source is not None else self.state.input.outside_source

            self.state.input.mode = normalized_mode
            self.state.input.inside_source = next_inside
            self.state.input.outside_source = next_outside
            self._set_playback_info_locked(normalized_mode, next_inside, next_outside)
            self._source_versions["inside"] += 1
            self._source_versions["outside"] += 1
            self._inside_monitor.reset()
            self._outside_monitor.reset()
            self._risk_engine.reset()
            self._recorded_validation = (
                validation_bundle if normalized_mode == "recorded" else self._empty_validation_bundle()
            )

        return self.get_input_config()

    def pause_processing(self) -> dict:
        with self._lock:
            self.state.input.enabled = False
            self.state.inside.available = False
            self.state.outside.available = False
            self.state.inside.status = "Stopped"
            self.state.outside.traffic_level = "Stopped"
            self.state.inside.confidence_note = "Processing stopped"
            self.state.outside.confidence_note = "Processing stopped"
            self.state.inside_fps = 0.0
            self.state.outside_fps = 0.0
            self.state.fused.score = 0
            self.state.fused.level = "Low"
            self.state.fused.reasons = ["Processing stopped"]
            self._inside_monitor.reset()
            self._outside_monitor.reset()
            self._risk_engine.reset()
        return self.get_input_config()

    def resume_processing(self) -> dict:
        with self._lock:
            self.state.input.enabled = True
        return self.get_input_config()

    async def save_uploaded_recording_stream(
        self,
        stream_name: str,
        filename: str,
        stream,
    ) -> dict:
        if stream_name not in {"inside", "outside"}:
            raise ValueError("Stream must be 'inside' or 'outside'.")

        safe_name = Path(filename or f"{stream_name}.mp4").name
        extension = Path(safe_name).suffix or ".mp4"
        if extension.lower() not in ALLOWED_VIDEO_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
            raise ValueError(f"Unsupported video type '{extension}'. Allowed types: {allowed}.")

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = self.settings.upload_dir / f"{stream_name}_{timestamp}{extension}"

        total_bytes = 0
        try:
            with open(target, "wb") as f:
                async for chunk in stream:
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if self.settings.upload_max_bytes > 0 and total_bytes > self.settings.upload_max_bytes:
                        max_mb = self.settings.upload_max_bytes / (1024 * 1024)
                        raise ValueError(f"Uploaded file is too large. Limit is {max_mb:.0f} MB.")
                    f.write(chunk)
        except Exception:
            if target.exists():
                target.unlink(missing_ok=True)
            raise

        if total_bytes == 0:
            if target.exists():
                target.unlink(missing_ok=True)
            raise ValueError("Uploaded file is empty.")

        target_path = str(target)
        self._pending_uploaded_sources[stream_name] = target_path
        validation = self._get_or_build_scene_validation(target_path, stream_name)
        bundle = self._build_recorded_validation_bundle(
            self._pending_uploaded_sources["inside"],
            self._pending_uploaded_sources["outside"],
        )
        with self._lock:
            self._recorded_validation = bundle
        return {
            "path": target_path,
            "validation": validation,
            "bundle": bundle,
        }

    def save_uploaded_recording(self, stream_name: str, filename: str, payload: bytes) -> dict:
        if stream_name not in {"inside", "outside"}:
            raise ValueError("Stream must be 'inside' or 'outside'.")
        if not payload:
            raise ValueError("Uploaded file is empty.")
        if self.settings.upload_max_bytes > 0 and len(payload) > self.settings.upload_max_bytes:
            max_mb = self.settings.upload_max_bytes / (1024 * 1024)
            raise ValueError(f"Uploaded file is too large. Limit is {max_mb:.0f} MB.")

        safe_name = Path(filename or f"{stream_name}.mp4").name
        extension = Path(safe_name).suffix or ".mp4"
        if extension.lower() not in ALLOWED_VIDEO_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
            raise ValueError(f"Unsupported video type '{extension}'. Allowed types: {allowed}.")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = self.settings.upload_dir / f"{stream_name}_{timestamp}{extension}"
        target.write_bytes(payload)
        target_path = str(target)
        self._pending_uploaded_sources[stream_name] = target_path
        validation = self._get_or_build_scene_validation(target_path, stream_name)
        bundle = self._build_recorded_validation_bundle(
            self._pending_uploaded_sources["inside"],
            self._pending_uploaded_sources["outside"],
        )
        with self._lock:
            self._recorded_validation = bundle
        return {
            "path": target_path,
            "validation": validation,
            "bundle": bundle,
        }

    def frame_stream(self, stream_name: str) -> Generator[bytes, None, None]:
        while not self._stop_event.is_set():
            with self._lock:
                frame = self._inside_frame.copy() if stream_name == "inside" else self._outside_frame.copy()
            success, encoded = cv2.imencode(".jpg", frame)
            if success:
                payload = encoded.tobytes()
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"
            time.sleep(0.05)

    def _inside_loop(self) -> None:
        self._stream_loop("inside", self.settings.inside_width, self.settings.inside_height, self._inside_monitor.analyze)

    def _outside_loop(self) -> None:
        self._stream_loop("outside", self.settings.outside_width, self.settings.outside_height, self._outside_monitor.analyze)

    def _stream_loop(self, stream_name: str, width: int, height: int, analyzer) -> None:
        cap = None
        frame_count = 0
        timer = time.perf_counter()
        active_version = -1
        last_mode = "live"

        while not self._stop_event.is_set():
            loop_started = time.perf_counter()
            with self._lock:
                source_value = self.state.input.inside_source if stream_name == "inside" else self.state.input.outside_source
                mode = self.state.input.mode
                version = self._source_versions[stream_name]
                enabled = self.state.input.enabled

            if not enabled:
                cap = self._reset_capture(cap)
                active_version = -1
                stopped_frame = self._placeholder_frame(f"{stream_name.title()} stream stopped")
                with self._lock:
                    if stream_name == "inside":
                        self._inside_frame = stopped_frame
                        self.state.inside.available = False
                        self.state.inside.status = "Stopped"
                        self.state.inside.confidence_note = "Processing stopped"
                    else:
                        self._outside_frame = stopped_frame
                        self.state.outside.available = False
                        self.state.outside.traffic_level = "Stopped"
                        self.state.outside.confidence_note = "Processing stopped"
                    self.state.inside_fps = 0.0
                    self.state.outside_fps = 0.0
                    self.state.fused.level = "Low"
                    self.state.fused.score = 0
                    self.state.fused.reasons = ["Processing stopped"]
                time.sleep(0.15)
                continue

            if version != active_version or mode != last_mode:
                cap = self._reset_capture(cap)
                active_version = version
                last_mode = mode

            if mode == "recorded" and not source_value.strip():
                cap = self._reset_capture(cap)
                ok, frame = False, None
            else:
                source = self._resolve_source(mode, source_value)
                cap = self._ensure_capture(cap, source, width, height)
                ok, frame = cap.read() if cap is not None else (False, None)

            if (not ok or frame is None) and mode == "recorded" and cap is not None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()

            if not ok or frame is None:
                fallback = self._build_unavailable_message(stream_name, mode, source_value)
                placeholder = self._placeholder_frame(fallback)
                if stream_name == "inside":
                    result_frame = placeholder
                    result_state = InsideState(
                        available=False,
                        face_detected=False,
                        status="Unavailable",
                        ear=0.0,
                        drowsy_frames=0,
                        confidence_note=fallback,
                    )
                else:
                    result_frame = placeholder
                    result_state = OutsideState(
                        available=False,
                        vehicle_count=0,
                        tracked_count=0,
                        close_vehicle=False,
                        traffic_level="Unavailable",
                        confidence_note=fallback,
                    )
                time.sleep(0.2)
                fps = 0.0
                progress = 0.0
                with self._lock:
                    if stream_name == "inside":
                        self._inside_frame = result_frame
                        self.state.inside = result_state
                        self.state.playback.inside_progress = progress
                        self.state.inside_fps = fps
                    else:
                        self._outside_frame = result_frame
                        self.state.outside = result_state
                        self.state.playback.outside_progress = progress
                        self.state.outside_fps = fps
                    self._update_fused_state_locked()
                continue

            result = analyzer(frame)
            frame_count += 1
            fps, frame_count, timer = self._compute_fps(frame_count, timer)
            progress = self._capture_progress(cap) if mode == "recorded" and cap is not None else 0.0
            with self._lock:
                if stream_name == "inside":
                    self._inside_frame = result.frame
                    self.state.inside = result.state
                    self.state.playback.inside_progress = progress
                    if fps is not None:
                        self.state.inside_fps = fps
                else:
                    self._outside_frame = result.frame
                    self.state.outside = result.state
                    self.state.playback.outside_progress = progress
                    if fps is not None:
                        self.state.outside_fps = fps
                self._update_fused_state_locked()

            if mode == "recorded" and cap is not None:
                self._pace_recorded_playback(cap, loop_started)

        self._reset_capture(cap)

    def _update_fused_state_locked(self) -> None:
        fused = self._risk_engine.evaluate(self.state.inside, self.state.outside)
        self.state.fused = fused
        if fused.level in {"High", "Critical"}:
            self._event_store.maybe_log_event(
                fused=fused,
                inside_state=self.state.inside,
                outside_state=self.state.outside,
                inside_frame=self._inside_frame,
                outside_frame=self._outside_frame,
            )

    @staticmethod
    def _compute_fps(frame_count: int, timer: float) -> tuple[float | None, int, float]:
        now = time.perf_counter()
        elapsed = now - timer
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            return round(fps, 1), 0, now
        return None, frame_count, timer

    @staticmethod
    def _ensure_capture(
        cap: cv2.VideoCapture | None,
        source: int | str,
        width: int,
        height: int,
    ) -> cv2.VideoCapture:
        if cap is not None and cap.isOpened():
            return cap
        cap = cv2.VideoCapture(source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        return cap

    @staticmethod
    def _reset_capture(cap: cv2.VideoCapture | None) -> None:
        if cap is not None:
            cap.release()
        return None

    @staticmethod
    def _resolve_source(mode: str, source_value: str) -> int | str:
        if mode == "live" and source_value.strip().isdigit():
            return int(source_value.strip())
        return source_value

    def _set_playback_info_locked(self, mode: str, inside_source: str, outside_source: str) -> None:
        if mode == "recorded":
            self.state.playback.inside_name = Path(inside_source).name
            self.state.playback.outside_name = Path(outside_source).name
        else:
            self.state.playback.inside_name = ""
            self.state.playback.outside_name = ""
        self.state.playback.inside_progress = 0.0
        self.state.playback.outside_progress = 0.0

    @staticmethod
    def _capture_progress(cap: cv2.VideoCapture) -> float:
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        current_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
        if total_frames <= 0:
            return 0.0
        progress = max(0.0, min((current_frame / total_frames) * 100.0, 100.0))
        return round(progress, 1)

    @staticmethod
    def _pace_recorded_playback(cap: cv2.VideoCapture, loop_started: float) -> None:
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        if source_fps <= 1 or source_fps > 60:
            source_fps = 25.0
        target_delay = 1.0 / source_fps
        elapsed = time.perf_counter() - loop_started
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)

    @staticmethod
    def _build_unavailable_message(stream_name: str, mode: str, source_value: str) -> str:
        stream_label = "Inside" if stream_name == "inside" else "Outside"
        if mode == "recorded" and not source_value.strip():
            return f"No {stream_label.lower()} recorded video selected"
        label = "camera" if mode == "live" else "video"
        return f"{stream_label} {label} unavailable: {source_value}"

    @staticmethod
    def _placeholder_frame(message: str) -> np.ndarray:
        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        frame[:] = (18, 25, 38)
        cv2.putText(frame, message, (40, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (236, 240, 241), 2)
        return frame

    @staticmethod
    def _validate_recorded_source(source_value: str, stream_name: str) -> None:
        if not Path(source_value).exists():
            raise ValueError(f"{stream_name.title()} video not found: {source_value}")

    def _prepare_recorded_sources(self, inside_source: str, outside_source: str) -> tuple[str, str]:
        inside_candidate = self._normalize_optional_recorded_source(inside_source)
        outside_candidate = self._normalize_optional_recorded_source(outside_source)

        if not inside_candidate and self._pending_uploaded_sources.get("inside"):
            pending_inside = self._pending_uploaded_sources["inside"]
            if Path(pending_inside).exists():
                inside_candidate = pending_inside

        if not outside_candidate and self._pending_uploaded_sources.get("outside"):
            pending_outside = self._pending_uploaded_sources["outside"]
            if Path(pending_outside).exists():
                outside_candidate = pending_outside

        if not inside_candidate and not outside_candidate:
            raise ValueError("Upload or enter at least one inside or outside video for recorded mode.")

        if inside_candidate:
            self._validate_recorded_source(inside_candidate, "inside")
        if outside_candidate:
            self._validate_recorded_source(outside_candidate, "outside")

        return inside_candidate, outside_candidate

    @staticmethod
    def _normalize_optional_recorded_source(source_value: str) -> str:
        stripped = source_value.strip()
        if stripped.isdigit():
            return ""
        return stripped

    @staticmethod
    def _empty_scene_validation(stream_name: str) -> dict:
        return {
            "stream": stream_name,
            "scene": "unknown",
            "confidence": 0.0,
            "face_ratio": 0.0,
            "vehicle_ratio": 0.0,
            "sampled_frames": 0,
            "warning": "",
            "summary": "No validation yet",
            "source": "",
        }

    def _empty_validation_bundle(self) -> dict:
        return {
            "inside": self._empty_scene_validation("inside"),
            "outside": self._empty_scene_validation("outside"),
            "warnings": [],
        }

    def _build_recorded_validation_bundle(self, inside_source: str, outside_source: str) -> dict:
        inside_validation = (
            self._get_or_build_scene_validation(inside_source, "inside")
            if inside_source
            else self._empty_scene_validation("inside")
        )
        outside_validation = (
            self._get_or_build_scene_validation(outside_source, "outside")
            if outside_source
            else self._empty_scene_validation("outside")
        )
        warnings = self._combine_validation_warnings(inside_validation, outside_validation)
        return {
            "inside": inside_validation,
            "outside": outside_validation,
            "warnings": warnings,
        }

    def _get_or_build_scene_validation(self, source_value: str, expected_stream: str) -> dict:
        if not source_value:
            return self._empty_scene_validation(expected_stream)
        cache_key = f"{expected_stream}:{source_value}"
        cached = self._validation_cache.get(cache_key)
        if cached is not None:
            return cached
        validation = self._inspect_recorded_scene(source_value, expected_stream)
        self._validation_cache[cache_key] = validation
        return validation

    def _combine_validation_warnings(self, inside_validation: dict, outside_validation: dict) -> list[str]:
        warnings: list[str] = []
        for validation in (inside_validation, outside_validation):
            if validation["warning"]:
                warnings.append(validation["warning"])

        inside_scene = inside_validation["scene"]
        outside_scene = outside_validation["scene"]
        if inside_scene == "road" and outside_scene == "cabin":
            warnings.insert(
                0,
                "Uploads look swapped: the inside stream appears road-facing and the outside stream appears cabin-facing.",
            )
        return list(dict.fromkeys(warnings))

    def _inspect_recorded_scene(self, source_value: str, expected_stream: str) -> dict:
        validation = self._empty_scene_validation(expected_stream)
        validation["source"] = source_value

        path = Path(source_value)
        if not path.exists():
            validation["warning"] = f"{expected_stream.title()} source does not exist for validation."
            validation["summary"] = validation["warning"]
            return validation

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            validation["warning"] = f"{expected_stream.title()} source could not be opened for validation."
            validation["summary"] = validation["warning"]
            return validation

        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            max_samples = max(self.settings.upload_validation_frames, 1)
            sample_positions = self._sample_positions(total_frames, max_samples)

            face_hits = 0
            vehicle_hits = 0
            sampled_frames = 0

            for frame_index in sample_positions:
                if total_frames > 0:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                sampled_frames += 1
                if self._frame_has_face(frame):
                    face_hits += 1
                if self._frame_has_vehicle(frame):
                    vehicle_hits += 1

            validation["sampled_frames"] = sampled_frames
            if sampled_frames == 0:
                validation["warning"] = f"{expected_stream.title()} source did not yield frames for validation."
                validation["summary"] = validation["warning"]
                return validation

            face_ratio = face_hits / sampled_frames
            vehicle_ratio = vehicle_hits / sampled_frames
            scene, confidence = self._classify_scene(face_ratio, vehicle_ratio, expected_stream)

            validation["scene"] = scene
            validation["confidence"] = round(confidence, 3)
            validation["face_ratio"] = round(face_ratio, 3)
            validation["vehicle_ratio"] = round(vehicle_ratio, 3)
            validation["warning"] = self._scene_warning(expected_stream, scene, confidence)
            validation["summary"] = (
                f"Scene looks {scene} | face frames {face_hits}/{sampled_frames} | "
                f"vehicle frames {vehicle_hits}/{sampled_frames}"
            )
            return validation
        finally:
            cap.release()

    @staticmethod
    def _sample_positions(total_frames: int, max_samples: int) -> list[int]:
        if total_frames <= 0:
            return list(range(max_samples))
        if total_frames <= max_samples:
            return list(range(total_frames))
        last_index = max(total_frames - 1, 1)
        return sorted({int((last_index * idx) / max(max_samples - 1, 1)) for idx in range(max_samples)})

    def _frame_has_face(self, frame: np.ndarray) -> bool:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._inside_monitor._face_mesh.process(rgb_frame)
        return bool(results.multi_face_landmarks)

    def _frame_has_vehicle(self, frame: np.ndarray) -> bool:
        if self._outside_monitor.model is None:
            return False
        inference = self._outside_monitor.model.predict(
            source=frame,
            conf=max(self.settings.yolo_confidence, 0.25),
            iou=self.settings.yolo_iou,
            imgsz=min(self.settings.yolo_imgsz, 640),
            device=self.settings.yolo_device,
            half=self.settings.yolo_half and self.settings.yolo_device != "cpu",
            verbose=False,
            classes=list(VEHICLE_CLASS_IDS),
        )
        if not inference:
            return False
        boxes = inference[0].boxes
        if boxes is None or len(boxes) == 0:
            return False
        xyxy_values = boxes.xyxy.int().cpu().tolist() if boxes.xyxy is not None else []
        for x1, y1, x2, y2 in xyxy_values:
            box_area = max((x2 - x1), 0) * max((y2 - y1), 0)
            if box_area >= self.settings.min_vehicle_box_area:
                return True
        return False

    def _classify_scene(
        self,
        face_ratio: float,
        vehicle_ratio: float,
        expected_stream: str = "",
    ) -> tuple[str, float]:
        face_threshold = self.settings.upload_validation_min_face_ratio
        vehicle_threshold = self.settings.upload_validation_min_vehicle_ratio

        has_face = face_ratio >= face_threshold
        has_vehicles = vehicle_ratio >= vehicle_threshold

        if expected_stream == "inside":
            # For inside cabin stream, detecting the driver's face is the primary validation signal.
            # Even if other vehicles are visible through windows/windshield, it is still a valid cabin stream.
            if has_face:
                return "cabin", face_ratio
            if has_vehicles and face_ratio < 0.2:
                return "road", vehicle_ratio
            if has_vehicles:
                return "mixed", vehicle_ratio
            return "unclear", max(face_ratio, vehicle_ratio)

        if expected_stream == "outside":
            # For outside road stream, vehicle/traffic detection is the primary validation signal.
            if has_vehicles and not has_face:
                return "road", vehicle_ratio
            if has_face and face_ratio > vehicle_ratio:
                return "cabin", face_ratio
            if has_vehicles:
                return "road", vehicle_ratio
            return "unclear", max(face_ratio, vehicle_ratio)

        if has_face and not has_vehicles:
            return "cabin", face_ratio
        if has_vehicles and not has_face:
            return "road", vehicle_ratio
        if has_face and has_vehicles:
            return "mixed", max(face_ratio, vehicle_ratio)
        return "unclear", max(face_ratio, vehicle_ratio)

    @staticmethod
    def _scene_warning(expected_stream: str, scene: str, confidence: float) -> str:
        if expected_stream == "inside" and scene == "road":
            return "Inside upload appears to be road footage. Check whether the streams were swapped."
        if expected_stream == "outside" and scene == "cabin":
            return "Outside upload appears to be cabin footage. Check whether the streams were swapped."
        if scene == "mixed":
            return "Scene has mixed visual cues. Review stream assignment if unexpected."
        if scene == "unclear" and confidence < 0.2:
            return "Scene validation is low confidence. Results may depend on camera angle or lighting."
        return ""
