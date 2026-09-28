from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class InputState:
    mode: str = "live"
    inside_source: str = "0"
    outside_source: str = "1"
    enabled: bool = False


@dataclass(slots=True)
class PlaybackState:
    inside_name: str = ""
    outside_name: str = ""
    inside_progress: float = 0.0
    outside_progress: float = 0.0


@dataclass(slots=True)
class InsideState:
    available: bool = False
    face_detected: bool = False
    status: str = "Waiting"
    ear: float = 0.0
    mar: float = 0.0
    attention_score: float = 1.0
    phone_detected: bool = False
    phone_confidence: float = 0.0
    yawning: bool = False
    distracted: bool = False
    drowsy_frames: int = 0
    yawn_frames: int = 0
    distraction_frames: int = 0
    confidence_note: str = "No frame yet"


@dataclass(slots=True)
class OutsideState:
    available: bool = False
    vehicle_count: int = 0
    tracked_count: int = 0
    close_vehicle: bool = False
    close_vehicle_count: int = 0
    proximity_score: float = 0.0
    class_counts: dict[str, int] = field(default_factory=dict)
    traffic_level: str = "Unknown"
    confidence_note: str = "No frame yet"


@dataclass(slots=True)
class FusedState:
    level: str = "Low"
    score: int = 0
    reasons: list[str] = field(default_factory=lambda: ["System starting"])


@dataclass(slots=True)
class SystemState:
    input: InputState = field(default_factory=InputState)
    playback: PlaybackState = field(default_factory=PlaybackState)
    inside: InsideState = field(default_factory=InsideState)
    outside: OutsideState = field(default_factory=OutsideState)
    fused: FusedState = field(default_factory=FusedState)
    inside_fps: float = 0.0
    outside_fps: float = 0.0
    started: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
