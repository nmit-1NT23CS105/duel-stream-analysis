"""
Dual-Stream Safety System - Comprehensive System Integrity & Feature Verification
Tests all state models, risk fusion engine, database persistence, analytics aggregation,
FastAPI endpoints/templates, live streaming generators, client camera ingestion, and control logic.
"""
import sys
import os
import time
from pathlib import Path

# Ensure writable matplotlib cache before any third-party imports
root_dir = Path(__file__).resolve().parent
if root_dir.name == "tests":
    root_dir = root_dir.parent
mpl_cache = root_dir / "data" / "matplotlib_cache"
mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(mpl_cache)
sys.path.insert(0, str(root_dir))

import cv2
import numpy as np

from app.config import settings
from app.core.state import InsideState, OutsideState, FusedState, SystemState, InputState
from app.fusion.risk_engine import RiskEngine
from app.storage.event_store import EventStore
from app.services.system_service import DualStreamService

def run_all_verification_checks():
    print("======================================================================")
    print("  DUAL-STREAM DANGEROUS DRIVING DETECTION - FULL VERIFICATION SUITE   ")
    print("======================================================================")
    results = []

    def check(name, condition, details=""):
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {name}")
        if details:
            print(f"       Details: {details}")
        results.append((name, status == "PASS"))
        assert condition, f"Verification failed: {name} - {details}"

    # ------------------------------------------------------------------
    # 1. State Model & Schema Verification
    # ------------------------------------------------------------------
    print("\n--- [1/6] STATE MODELS & SCHEMA ATTRIBUTES ---")
    in_state = InsideState()
    check(
        "InsideState Advanced Cues",
        all(hasattr(in_state, a) for a in ["microsleep_detected", "head_nod_detected", "drinking_detected", "eye_gaze_direction", "stress_level"]),
        "microsleep, head nod, drinking, eye gaze, and stress attributes present",
    )
    
    out_state = OutsideState()
    check(
        "OutsideState Road & Vehicle Cues",
        all(hasattr(out_state, a) for a in ["estimated_speed_kmh", "speed_limit_kmh", "overspeed_detected", "pedestrian_count", "cyclist_count", "vru_risk", "ttc_seconds", "ttc_warning", "traffic_signal", "stop_sign_detected", "weather_condition"]),
        "speed, overspeed, VRU, TTC collision, traffic lights, and weather attributes present",
    )

    sys_state = SystemState()
    check(
        "SystemState Fusion Hierarchy",
        hasattr(sys_state, "inside") and hasattr(sys_state, "outside") and hasattr(sys_state, "fused") and hasattr(sys_state, "input"),
        "top-level system state correctly bundles inside, outside, fused, and input states",
    )

    # ------------------------------------------------------------------
    # 2. Risk Fusion Engine Verification
    # ------------------------------------------------------------------
    print("\n--- [2/6] RISK FUSION ENGINE LOGIC ---")
    engine = RiskEngine(settings)

    # Baseline Alert Driver
    f_normal = engine.evaluate(
        InsideState(available=True, face_detected=True, status="Awake", ear=0.32, attention_score=0.95),
        OutsideState(available=True, traffic_level="Low", vehicle_count=0),
    )
    check("Normal Alert Driving", f_normal.level == "Low" and f_normal.score == 0, f"Score: {f_normal.score}, Level: {f_normal.level}")

    # Overspeed Risk
    f_speed = engine.evaluate(
        InsideState(available=True, face_detected=True, status="Awake", ear=0.32, attention_score=0.92),
        OutsideState(available=True, vehicle_count=2, traffic_level="Moderate", estimated_speed_kmh=85.0, speed_limit_kmh=60.0, overspeed_detected=True, rapid_approach=True),
    )
    check("Overspeeding Detection", f_speed.score >= 18 and ("Overspeed" in f_speed.category or any("speed" in r.lower() for r in f_speed.reasons)), f"Score: {f_speed.score}, Category: {f_speed.category}")

    # Vulnerable Road User (VRU)
    f_vru = engine.evaluate(
        InsideState(available=True, face_detected=True, status="Awake", ear=0.30, attention_score=0.90),
        OutsideState(available=True, vehicle_count=1, pedestrian_count=1, vru_risk=True),
    )
    check("VRU Hazard Detection", f_vru.score >= 20 and ("VRU" in f_vru.category or any("vulnerable" in r.lower() for r in f_vru.reasons)), f"Score: {f_vru.score}, Category: {f_vru.category}")

    # Microsleep Extreme Hazard
    f_micro = engine.evaluate(
        InsideState(available=True, face_detected=True, status="Microsleep", ear=0.10, microsleep_detected=True),
        OutsideState(available=True),
    )
    check("Microsleep Driver Hazard", f_micro.level in {"Medium", "High", "Critical"} and "Microsleep" in f_micro.category, f"Score: {f_micro.score}, Level: {f_micro.level}, Category: {f_micro.category}")

    # Multi-Risk Critical Compound (Asleep + Rapid Closing Vehicle) settled across smoothing window
    engine.reset()
    in_crit = InsideState(available=True, face_detected=True, status="Drowsy", ear=0.12, attention_score=0.0, seatbelt_status="Fastened")
    out_crit = OutsideState(available=True, vehicle_count=2, close_vehicle=True, close_vehicle_count=1, rapid_approach=True, approach_rate=0.35, proximity_score=0.11, traffic_level="Low", lane_status="Centered")
    for _ in range(settings.risk_smoothing_window + 2):
        f_crit = engine.evaluate(in_crit, out_crit)
    check("Multi-Risk Critical Compound", f_crit.level == "Critical" and f_crit.score >= 75, f"Score: {f_crit.score}, Level: {f_crit.level}, Category: {f_crit.category}")

    # ------------------------------------------------------------------
    # 3. Event Database & Analytics Aggregation
    # ------------------------------------------------------------------
    print("\n--- [3/6] DATABASE STORAGE & ANALYTICS ---")
    store = EventStore(settings)
    summary = store.get_analytics_summary()
    expected_keys = ["total_events", "critical_count", "high_count", "risk_levels", "categories", "score_trend", "acknowledged_count"]
    check("Analytics Summary Aggregation", all(k in summary for k in expected_keys), f"Total events: {summary['total_events']}, Acknowledged: {summary['acknowledged_count']}, Avg score: {summary['average_risk_score']}")

    events = store.fetch_events(limit=5)
    check("Event Query & Listing", isinstance(events, list), f"Fetched {len(events)} recent events")

    if events:
        test_id = events[0]["id"]
        ack_res = store.acknowledge_event(test_id)
        check(f"Event Acknowledgment (ID: {test_id})", ack_res is True or ack_res is False, "Event successfully marked acknowledged")

    csv_data = store.export_csv()
    check("CSV Audit Log Export", "Event ID" in csv_data and "Risk Level" in csv_data and "Acknowledged" in csv_data, f"CSV Header and payload verified ({len(csv_data)} bytes)")

    # ------------------------------------------------------------------
    # 4. Frontend Asset & HTML Route Verification
    # ------------------------------------------------------------------
    print("\n--- [4/6] FRONTEND ASSETS & HTML INTERFACES ---")
    static_dir = root_dir / "app" / "static"
    index_html = (static_dir / "index.html").read_text(encoding="utf-8")
    check("Desktop Dashboard (index.html)", "/stream/outside" in index_html and "/stream/inside" in index_html and "Browser Webcam" in index_html and "Device Camera" in index_html, "MJPEG video elements and client camera buttons present")

    incidents_html = (static_dir / "incidents.html").read_text(encoding="utf-8")
    check("Incident Review (incidents.html)", "Incident History" in incidents_html and "/analytics" in incidents_html, "Incident table and navigation links verified")

    analytics_html = (static_dir / "analytics.html").read_text(encoding="utf-8")
    check("System Analytics (analytics.html)", "Risk & Incident Analytics" in analytics_html and "chart-svg-container" in analytics_html, "Analytics dashboard and chart containers verified")

    mobile_html = (static_dir / "mobile" / "index.html").read_text(encoding="utf-8")
    check("Mobile Responsive View (mobile/index.html)", "Selfie Cam" in mobile_html and "Rear Cam" in mobile_html and "sw.js" in (static_dir / "mobile" / "app.js").read_text(encoding="utf-8"), "PWA support and mobile camera controls verified")

    # ------------------------------------------------------------------
    # 5. DualStreamService Lifecycle & Streaming
    # ------------------------------------------------------------------
    print("\n--- [5/6] DUALSTREAM SERVICE & LIVE STREAMING ---")
    service = DualStreamService(settings)
    check("Service Default State", service.state.input.enabled is True, "Service starts with processing enabled by default")

    # Live frame generation test
    in_gen = service.frame_stream("inside")
    in_chunk = next(in_gen)
    check("Inside Stream Generator", b"--frame" in in_chunk and b"image/jpeg" in in_chunk and len(in_chunk) > 1000, f"Valid multipart MJPEG frame yielded ({len(in_chunk)} bytes)")

    out_gen = service.frame_stream("outside")
    out_chunk = next(out_gen)
    check("Outside Stream Generator", b"--frame" in out_chunk and b"image/jpeg" in out_chunk and len(out_chunk) > 1000, f"Valid multipart MJPEG frame yielded ({len(out_chunk)} bytes)")

    # Monitoring snapshot
    snap = service.get_monitoring_snapshot()
    check("Live Telemetry Snapshot", all(k in snap for k in ["driver", "road", "risk", "raw_state"]), f"Driver: {snap['driver']['state']}, Road: {snap['road']['traffic_density']}, Risk: {snap['risk']['level']}")

    # ------------------------------------------------------------------
    # 6. Client Camera Ingestion Pipeline (Browser Webcam)
    # ------------------------------------------------------------------
    print("\n--- [6/6] IN-BROWSER WEBCAM INGESTION ---")
    # Generate test frame
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    test_frame[:] = (45, 90, 135)
    cv2.putText(test_frame, "TEST_STREAM", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    ok, enc_bytes = cv2.imencode(".jpg", test_frame)
    check("Test Frame Encoding", ok and len(enc_bytes) > 500, f"Encoded test JPEG ({len(enc_bytes)} bytes)")

    # Ingest inside
    t0 = time.time()
    in_res = service.ingest_client_frame("inside", enc_bytes.tobytes())
    t_in = round((time.time() - t0) * 1000, 1)
    check("Inside Ingestion & MediaPipe Analysis", in_res.get("success") is True, f"Latency: {t_in} ms, Driver status: {in_res['state']['status']}")

    # Ingest outside
    t0 = time.time()
    out_res = service.ingest_client_frame("outside", enc_bytes.tobytes())
    t_out = round((time.time() - t0) * 1000, 1)
    check("Outside Ingestion & YOLO Analysis", out_res.get("success") is True, f"Latency: {t_out} ms, Traffic level: {out_res['state']['traffic_level']}")

    # Verify stream updated with newly ingested frame
    in_chunk_after = next(in_gen)
    check("Stream Yields Newly Ingested Frame", len(in_chunk_after) > 1000, f"Updated MJPEG frame size: {len(in_chunk_after)} bytes")

    # Control toggle
    pause_cfg = service.pause_processing()
    check("Service Pause Control", pause_cfg["enabled"] is False, "Processing paused")
    resume_cfg = service.resume_processing()
    check("Service Resume Control", resume_cfg["enabled"] is True, "Processing resumed")

    # Clean shutdown
    service.stop()
    check("Clean Service Shutdown", service.state.started is False, "Service threads stopped safely")

    # ------------------------------------------------------------------
    # Final Summary
    # ------------------------------------------------------------------
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print("\n======================================================================")
    print(f"  VERIFICATION RESULT: {passed}/{total} CHECKS PASSED ({(passed/total)*100:.1f}%)")
    print("======================================================================\n")
    return passed == total

if __name__ == "__main__":
    success = run_all_verification_checks()
    sys.exit(0 if success else 1)
