from __future__ import annotations

from collections import deque

from app.config import Settings
from app.core.state import FusedState, InsideState, OutsideState


class RiskEngine:
    """Combines inside and outside observations into a preliminary Phase 1 risk level."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._score_history: deque[int] = deque(maxlen=max(settings.risk_smoothing_window, 1))

    def reset(self) -> None:
        self._score_history.clear()

    @staticmethod
    def _level_from_score(score: int) -> str:
        if score >= 85:
            return "Critical"
        if score >= 60:
            return "High"
        if score >= 30:
            return "Medium"
        return "Low"

    def evaluate(self, inside: InsideState, outside: OutsideState) -> FusedState:
        score = 0
        reasons: list[str] = []

        if not inside.available:
            reasons.append("Inside stream unavailable")
        elif inside.status == "Fatigue Risk":
            score += 46
            reasons.append(
                f"Fatigue risk: EAR {inside.ear:.2f}, MAR {inside.mar:.2f}, attention {inside.attention_score:.2f}"
            )
        elif inside.status == "Drowsy":
            score += 48
            reasons.append(f"Low EAR detected ({inside.ear:.2f})")
        elif inside.status == "Distracted":
            score += 34
            reasons.append(f"Driver attention dropped ({inside.attention_score:.2f})")
        elif inside.status == "Phone Use":
            score += 30
            reasons.append(f"Possible handheld phone usage detected ({inside.phone_confidence:.2f})")
        elif inside.status == "Yawning":
            score += 18
            reasons.append(f"Sustained yawn detected ({inside.mar:.2f})")
        elif inside.status == "No Face":
            score += 12
            reasons.append("Driver face not visible")
        elif inside.status == "Monitoring":
            score += 5
            reasons.append("Driver face visible but confidence is low")
        else:
            reasons.append(
                f"Driver appears awake (EAR {inside.ear:.2f}, attention {inside.attention_score:.2f})"
            )

        if not outside.available:
            reasons.append("Outside stream unavailable")
        elif outside.close_vehicle_count >= 2:
            score += 36
            reasons.append(f"{outside.close_vehicle_count} close vehicles detected ahead")
        elif outside.close_vehicle:
            score += 24
            reasons.append("Vehicle detected in close front zone")
        elif outside.vehicle_count >= 6:
            score += 18
            reasons.append(f"Dense surrounding traffic ({outside.vehicle_count} visible)")
        elif outside.vehicle_count > 0:
            score += 8
            reasons.append(f"Vehicles detected around ego view ({outside.vehicle_count})")
        else:
            reasons.append("Outside road appears clear")

        if outside.proximity_score >= 0.09:
            score += 12
            reasons.append(f"Large nearby vehicle footprint ({outside.proximity_score:.2f})")
        elif outside.proximity_score >= 0.05:
            score += 6
            reasons.append(f"Nearby vehicle footprint rising ({outside.proximity_score:.2f})")

        if outside.lane_status in {"Drifting Left", "Drifting Right"}:
            score += 18
            reasons.append(f"Vehicle lane departure detected ({outside.lane_status})")

        if outside.weaving_detected:
            score += 30
            reasons.append("Aggressive weaving detected across road lanes")

        if outside.sudden_lane_change:
            score += 20
            reasons.append("Abrupt lateral shift / sudden lane change detected")

        if outside.rapid_approach:
            score += 24
            reasons.append(f"Front vehicle closing rapidly (+{int(outside.approach_rate*100)}%)")

        if inside.phone_detected and inside.status != "Phone Use":
            score += 18
            reasons.append(f"Phone usage signal present ({inside.phone_confidence:.2f})")

        if inside.phone_duration_sec >= 3.0:
            score += 20
            reasons.append(f"Sustained handheld phone use ({inside.phone_duration_sec:.1f}s)")

        if inside.perclos >= 25.0:
            score += 22
            reasons.append(f"Elevated PERCLOS ({inside.perclos:.1f}%) indicates cumulative fatigue")

        if outside.aggressive_driving_detected:
            score += 28
            reasons.append(f"Aggressive driving behavior score elevated ({outside.aggressive_driving_score}/100)")

        if inside.available and inside.face_detected and inside.seatbelt_status == "Unfastened":
            score += 15
            reasons.append("Driver seatbelt is not fastened")

        # Contextual synergy rules
        if outside.rapid_approach and inside.status in {"Drowsy", "Fatigue Risk"}:
            score += 30
            reasons.append("CRITICAL: Vehicle closing rapidly while driver is fatigued")
        elif outside.rapid_approach and (inside.status == "Distracted" or inside.phone_detected):
            score += 26
            reasons.append("HIGH RISK: Vehicle closing rapidly while driver is distracted")

        if outside.lane_status in {"Drifting Left", "Drifting Right", "Repeated Weaving"} and inside.status in {"Drowsy", "Fatigue Risk"}:
            score += 25
            reasons.append("CRITICAL: Lane departure/weaving while driver is fatigued")
        elif outside.lane_status in {"Drifting Left", "Drifting Right", "Repeated Weaving"} and (inside.status == "Distracted" or inside.phone_detected):
            score += 22
            reasons.append("HIGH RISK: Lane departure/weaving while driver is distracted or on phone")

        if inside.status in {"Drowsy", "Fatigue Risk"} and outside.close_vehicle:
            score += 25
            reasons.append("Fatigued driver with close front vehicle")
        elif inside.phone_detected and outside.close_vehicle:
            score += 20
            reasons.append("Phone use detected with close front vehicle")
        elif inside.status == "Distracted" and outside.close_vehicle:
            score += 18
            reasons.append("Distracted driver with close front vehicle")
        elif inside.seatbelt_status == "Unfastened" and outside.close_vehicle:
            score += 15
            reasons.append("Unfastened seatbelt with close vehicle ahead")
        elif inside.status == "Yawning" and outside.vehicle_count >= 4:
            score += 10
            reasons.append("Yawning driver in active traffic")
        elif inside.phone_detected and outside.vehicle_count >= 4:
            score += 22
            reasons.append("Phone use detected in active traffic")
        elif inside.status == "Distracted" and outside.vehicle_count >= 4:
            score += 10
            reasons.append("Distracted driver in active traffic")
        elif inside.seatbelt_status == "Unfastened" and outside.vehicle_count >= 4:
            score += 10
            reasons.append("Unfastened seatbelt in active traffic")
        elif inside.status == "No Face" and outside.close_vehicle:
            score += 12
            reasons.append("Face missing while front vehicle is close")

        # Determine incident category (P2-FR10)
        categories: list[str] = []
        if inside.status in {"Fatigue Risk", "Drowsy", "Yawning"} or inside.perclos >= 25.0:
            categories.append("Fatigue")
        if inside.phone_detected:
            categories.append("Phone Use")
        if inside.status == "Distracted" or inside.head_pose_direction in {"Left", "Right", "Down"}:
            categories.append("Distraction")
        if outside.weaving_detected or outside.sudden_lane_change or outside.aggressive_driving_detected:
            categories.append("Aggressive Driving")
        if outside.lane_status in {"Drifting Left", "Drifting Right"}:
            categories.append("Lane Departure")
        if outside.close_vehicle or outside.rapid_approach:
            categories.append("Tailgating / Proximity")
        if inside.available and inside.face_detected and inside.seatbelt_status == "Unfastened":
            categories.append("Seatbelt Violation")

        if len(categories) > 1:
            category = "Multi-Risk (" + " + ".join(categories[:2]) + ")"
        elif len(categories) == 1:
            category = categories[0]
        else:
            category = "Normal Driving"

        # Calculate confidence metric (P2-FR10)
        conf = 0.85
        if inside.available and inside.face_detected:
            conf = min(0.95, conf + 0.10)
        if outside.available and outside.vehicle_count > 0:
            conf = min(0.98, conf + 0.05)

        raw_score = min(score, 100)
        raw_level = self._level_from_score(raw_score)
        self._score_history.append(raw_score)

        smoothed_score = int(round(sum(self._score_history) / len(self._score_history)))
        high_hits = sum(1 for value in self._score_history if value >= 60)
        critical_hits = sum(1 for value in self._score_history if value >= 85)

        level = self._level_from_score(smoothed_score)
        if raw_level == "Critical" and critical_hits < self.settings.critical_persistence_frames:
            level = "High"
            reasons.append("Critical risk held until it persists across frames")
        elif raw_level in {"High", "Critical"} and high_hits < self.settings.high_persistence_frames:
            level = "Medium"
            reasons.append("Elevated risk held until it stabilizes across frames")
        elif smoothed_score != raw_score:
            reasons.append(f"Temporal smoothing applied ({raw_score} -> {smoothed_score})")

        return FusedState(level=level, score=smoothed_score, category=category, confidence=round(conf, 2), reasons=reasons)
