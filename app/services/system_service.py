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
from app.models.outside_monitor import OutsideMonitor
from app.storage.event_store import EventStore


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
        search: str | None = None,
    ) -> list[dict]:
        return self._event_store.fetch_events(limit=limit, risk_level=risk_level, search=search)

    def get_input_config(self) -> dict:
        with self._lock:
            return {
                "mode": self.state.input.mode,
                "inside_source": self.state.input.inside_source,
                "outside_source": self.state.input.outside_source,
                "enabled": self.state.input.enabled,
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

        with self._lock:
            next_inside = inside_source.strip() if inside_source is not None else self.state.input.inside_source
            next_outside = outside_source.strip() if outside_source is not None else self.state.input.outside_source

            if normalized_mode == "recorded":
                next_inside, next_outside = self._prepare_recorded_sources(next_inside, next_outside)

            self.state.input.mode = normalized_mode
            self.state.input.inside_source = next_inside
            self.state.input.outside_source = next_outside
            self._set_playback_info_locked(normalized_mode, next_inside, next_outside)
            self._source_versions["inside"] += 1
            self._source_versions["outside"] += 1
            self._inside_monitor.reset()
            self._outside_monitor.reset()
            self._risk_engine.reset()

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

    def save_uploaded_recording(self, stream_name: str, filename: str, payload: bytes) -> str:
        if stream_name not in {"inside", "outside"}:
            raise ValueError("Stream must be 'inside' or 'outside'.")
        if not payload:
            raise ValueError("Uploaded file is empty.")

        safe_name = Path(filename or f"{stream_name}.mp4").name
        extension = Path(safe_name).suffix or ".mp4"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = self.settings.upload_dir / f"{stream_name}_{timestamp}{extension}"
        target.write_bytes(payload)
        return str(target)

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

    @classmethod
    def _prepare_recorded_sources(cls, inside_source: str, outside_source: str) -> tuple[str, str]:
        inside_candidate = cls._normalize_optional_recorded_source(inside_source)
        outside_candidate = cls._normalize_optional_recorded_source(outside_source)

        if not inside_candidate and not outside_candidate:
            raise ValueError("Upload or enter at least one inside or outside video for recorded mode.")

        if inside_candidate:
            cls._validate_recorded_source(inside_candidate, "inside")
        if outside_candidate:
            cls._validate_recorded_source(outside_candidate, "outside")

        return inside_candidate, outside_candidate

    @staticmethod
    def _normalize_optional_recorded_source(source_value: str) -> str:
        stripped = source_value.strip()
        if stripped.isdigit():
            return ""
        return stripped
