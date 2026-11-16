"""
Dual-Stream Safety System - Comprehensive System Integrity & Feature Verification
Tests state objects, risk fusion, database acknowledgment, analytics, and service logic.
"""
import sys
import os
import asyncio
from pathlib import Path

# Ensure app is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.core.state import InsideState, OutsideState
from app.fusion.risk_engine import RiskEngine
from app.storage.event_store import EventStore
from app.main import (
    service,
    index,
    incidents_page,
    analytics_page,
    mobile_page,
    get_state,
    get_events,
    get_analytics,
    acknowledge_event,
    export_events_csv,
)

async def run_async_checks():
    print("======================================================================")
    print("  RUNNING SYSTEM INTEGRITY & FEATURE VERIFICATION SUITE")
    print("======================================================================")

    # 1. State Model Verification
    print("\n[1/5] Verifying State Models & New Feature Attributes...")
    in_state = InsideState()
    assert hasattr(in_state, "microsleep_detected"), "Missing microsleep_detected"
    assert hasattr(in_state, "head_nod_detected"), "Missing head_nod_detected"
    assert hasattr(in_state, "drinking_detected"), "Missing drinking_detected"
    assert hasattr(in_state, "eye_gaze_direction"), "Missing eye_gaze_direction"
    assert hasattr(in_state, "stress_level"), "Missing stress_level"
    
    out_state = OutsideState()
    assert hasattr(out_state, "estimated_speed_kmh"), "Missing estimated_speed_kmh"
    assert hasattr(out_state, "speed_limit_kmh"), "Missing speed_limit_kmh"
    assert hasattr(out_state, "overspeed_detected"), "Missing overspeed_detected"
    assert hasattr(out_state, "speed_status"), "Missing speed_status"
    assert hasattr(out_state, "pedestrian_count"), "Missing pedestrian_count"
    assert hasattr(out_state, "cyclist_count"), "Missing cyclist_count"
    assert hasattr(out_state, "vru_risk"), "Missing vru_risk"
    assert hasattr(out_state, "ttc_seconds"), "Missing ttc_seconds"
    assert hasattr(out_state, "ttc_warning"), "Missing ttc_warning"
    assert hasattr(out_state, "traffic_signal"), "Missing traffic_signal"
    assert hasattr(out_state, "stop_sign_detected"), "Missing stop_sign_detected"
    assert hasattr(out_state, "weather_condition"), "Missing weather_condition"
    print("  -> InsideState & OutsideState advanced attributes verified.")

    # 2. Risk Fusion Engine with Overspeed, VRU, and Microsleep
    print("\n[2/5] Verifying Risk Fusion Engine with New Hazard Signals...")
    engine = RiskEngine(settings)
    in_normal = InsideState(available=True, face_detected=True, status="Awake", ear=0.32, attention_score=0.95)
    out_speeding = OutsideState(
        available=True,
        vehicle_count=2,
        traffic_level="Moderate",
        estimated_speed_kmh=85.0,
        speed_limit_kmh=60.0,
        overspeed_detected=True,
        rapid_approach=True
    )
    fused_speed = engine.evaluate(in_normal, out_speeding)
    assert "Overspeeding" in fused_speed.category or "Overspeed" in str(fused_speed.reasons), "Overspeed not reflected"
    assert fused_speed.score >= 18, "Overspeed score not applied"
    print(f"  -> Overspeed: Score={fused_speed.score}, Category={fused_speed.category} [OK]")

    # VRU Risk evaluation
    out_vru = OutsideState(available=True, vehicle_count=1, pedestrian_count=1, vru_risk=True)
    fused_vru = engine.evaluate(in_normal, out_vru)
    assert "VRU" in fused_vru.category or "Vulnerable Road User" in str(fused_vru.reasons), "VRU not reflected"
    print(f"  -> VRU Hazard: Score={fused_vru.score}, Category={fused_vru.category} [OK]")

    # Microsleep evaluation
    in_microsleep = InsideState(available=True, face_detected=True, status="Microsleep", ear=0.10, microsleep_detected=True)
    out_clear = OutsideState(available=True)
    fused_micro = engine.evaluate(in_microsleep, out_clear)
    assert "Microsleep" in fused_micro.category or "Microsleep" in str(fused_micro.reasons), "Microsleep not reflected"
    print(f"  -> Microsleep Hazard: Score={fused_micro.score}, Category={fused_micro.category} [OK]")

    # 3. Database & Analytics Summary
    print("\n[3/5] Verifying Event Store & Analytics Aggregation...")
    db_path = Path("data/events.db")
    store = EventStore(db_path=db_path)
    summary = store.get_analytics_summary()
    assert "total_events" in summary, "Missing total_events in analytics summary"
    assert "risk_distribution" in summary, "Missing risk_distribution in summary"
    assert "trend" in summary, "Missing trend in summary"
    assert "acknowledgment_rate" in summary, "Missing acknowledgment_rate in summary"
    print(f"  -> Total stored events: {summary['total_events']}")
    print(f"  -> Acknowledged count: {summary['acknowledged_count']}")
    print(f"  -> Acknowledgment rate: {summary['acknowledgment_rate']}%")
    print("  -> Event Store analytics verified.")

    # 4. FastAPI Handler Endpoints
    print("\n[4/5] Verifying FastAPI HTTP Route Handlers...")

    # Dashboard
    res_dash = await index()
    dash_content = Path(res_dash.path).read_text(encoding="utf-8")
    assert "/analytics" in dash_content, "Dashboard missing /analytics link"
    print("  -> index() [OK] (contains Analytics navigation)")

    # Incidents page
    res_inc = await incidents_page()
    inc_content = Path(res_inc.path).read_text(encoding="utf-8")
    assert "/analytics" in inc_content, "Incidents page missing /analytics link"
    print("  -> incidents_page() [OK] (contains Analytics navigation)")

    # Analytics page
    res_ana = await analytics_page()
    ana_content = Path(res_ana.path).read_text(encoding="utf-8")
    assert "System Analytics" in ana_content, "Analytics page title missing"
    print("  -> analytics_page() [OK]")

    # Mobile page
    res_mob = await mobile_page()
    mob_content = Path(res_mob.path).read_text(encoding="utf-8")
    assert "/analytics" in mob_content, "Mobile page missing /analytics link"
    print("  -> mobile_page() [OK]")

    # State API
    res_state = await get_state()
    assert "fused" in res_state and "inside" in res_state and "outside" in res_state
    print("  -> get_state() [OK]")

    # Events API
    res_events = await get_events(limit=10)
    assert "events" in res_events
    print(f"  -> get_events() [OK] ({len(res_events['events'])} events returned)")

    # Analytics API
    res_api_ana = await get_analytics()
    assert res_api_ana["status"] == "ok"
    assert "data" in res_api_ana
    print("  -> get_analytics() [OK]")

    # CSV Export API
    res_csv = await export_events_csv()
    csv_text = res_csv.body.decode("utf-8")
    assert "Acknowledged" in csv_text, "CSV export missing Acknowledged column"
    print("  -> export_events_csv() [OK] (CSV header contains 'Acknowledged')")

    # Acknowledge API
    if res_events["events"]:
        test_id = res_events["events"][0]["id"]
        res_ack = await acknowledge_event(test_id)
        assert res_ack.status_code in (200, 404), f"Unexpected status: {res_ack.status_code}"
        print(f"  -> acknowledge_event({test_id}) [OK] (status {res_ack.status_code})")

    # 5. Monitoring Snapshot & WebSocket payload structure
    print("\n[5/5] Verifying Structured Live Snapshot (/ws/monitoring)...")
    snapshot = service.get_monitoring_snapshot()
    assert "driver" in snapshot, "Snapshot missing driver block"
    assert "road" in snapshot, "Snapshot missing road block"
    assert "risk" in snapshot, "Snapshot missing risk block"
    assert "raw_state" in snapshot, "Snapshot missing raw_state block"
    print(f"  -> Monitoring snapshot:")
    print(f"     Driver: {snapshot['driver']['status']}, Road density: {snapshot['road']['traffic_density']}, Risk: {snapshot['risk']['level']} ({snapshot['risk']['score']})")
    print("  -> Monitoring snapshot verified [OK]")

    print("\n======================================================================")
    print("  ALL VERIFICATION CHECKS PASSED SUCCESSFULLY (100%)")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(run_async_checks())
