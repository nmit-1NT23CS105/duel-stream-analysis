from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import threading
import time
from urllib.parse import quote

import cv2

from app.config import Settings
from app.core.state import FusedState, InsideState, OutsideState


class EventStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._last_logged_at = 0.0
        self._last_signature = ""
        self.settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def maybe_log_event(
        self,
        fused: FusedState,
        inside_state: InsideState,
        outside_state: OutsideState,
        inside_frame,
        outside_frame,
    ) -> None:
        signature = self._build_signature(fused, inside_state, outside_state)
        now = time.time()

        with self._lock:
            if (
                signature == self._last_signature
                and now - self._last_logged_at < self.settings.high_event_cooldown_sec
            ):
                return None
            self._last_signature = signature
            self._last_logged_at = now

        event_id = self._insert_event(
            fused=fused,
            inside_state=inside_state,
            outside_state=outside_state,
        )

        inside_snapshot_name = self._save_snapshot(event_id, "inside", inside_frame)
        outside_snapshot_name = self._save_snapshot(event_id, "outside", outside_frame)
        self._attach_snapshots(event_id, inside_snapshot_name, outside_snapshot_name)
        return None

    def fetch_recent(self, limit: int = 10) -> list[dict]:
        return self.fetch_events(limit=limit)

    def fetch_events(
        self,
        limit: int = 24,
        risk_level: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        normalized_limit = max(int(limit), 1)
        clauses: list[str] = []
        params: list[object] = []

        if risk_level:
            clauses.append("UPPER(risk_level) = UPPER(?)")
            params.append(risk_level)

        if category:
            clauses.append("UPPER(category) LIKE UPPER(?)")
            params.append(f"%{category}%")

        if search:
            clauses.append(
                "(created_at LIKE ? OR category LIKE ? OR inside_status LIKE ? OR outside_traffic LIKE ? OR reasons_json LIKE ?)"
            )
            term = f"%{search}%"
            params.extend([term, term, term, term, term])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT
                id,
                created_at,
                risk_level,
                risk_score,
                category,
                confidence,
                inside_status,
                outside_traffic,
                reasons_json,
                inside_snapshot,
                outside_snapshot
            FROM events
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(normalized_limit)

        with sqlite3.connect(self.settings.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_event(row) for row in rows]

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.settings.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Normal Driving',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    inside_status TEXT NOT NULL,
                    outside_traffic TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    inside_snapshot TEXT,
                    outside_snapshot TEXT
                )
                """
            )
            # Automatic schema migration
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
            if "category" not in existing_cols:
                conn.execute("ALTER TABLE events ADD COLUMN category TEXT NOT NULL DEFAULT 'Normal Driving'")
            if "confidence" not in existing_cols:
                conn.execute("ALTER TABLE events ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0")
            conn.commit()

    def _insert_event(
        self,
        fused: FusedState,
        inside_state: InsideState,
        outside_state: OutsideState,
    ) -> int:
        created_at = datetime.now().isoformat(timespec="seconds")
        reasons_json = json.dumps(fused.reasons)
        with sqlite3.connect(self.settings.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO events (
                    created_at,
                    risk_level,
                    risk_score,
                    category,
                    confidence,
                    inside_status,
                    outside_traffic,
                    reasons_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    fused.level,
                    fused.score,
                    fused.category,
                    fused.confidence,
                    inside_state.status,
                    outside_state.traffic_level,
                    reasons_json,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _attach_snapshots(
        self,
        event_id: int,
        inside_snapshot: str | None,
        outside_snapshot: str | None,
    ) -> None:
        with sqlite3.connect(self.settings.db_path) as conn:
            conn.execute(
                """
                UPDATE events
                SET inside_snapshot = ?, outside_snapshot = ?
                WHERE id = ?
                """,
                (inside_snapshot, outside_snapshot, event_id),
            )
            conn.commit()

    def _save_snapshot(self, event_id: int, stream_name: str, frame) -> str | None:
        if frame is None:
            return None

        snapshot_name = f"event_{event_id}_{stream_name}.jpg"
        snapshot_path = self.settings.snapshot_dir / snapshot_name
        success = cv2.imwrite(str(snapshot_path), frame)
        if not success:
            return None
        return snapshot_name

    @staticmethod
    def _build_signature(
        fused: FusedState,
        inside_state: InsideState,
        outside_state: OutsideState,
    ) -> str:
        raw = "|".join(
            [
                fused.level,
                inside_state.status,
                str(inside_state.phone_detected),
                outside_state.traffic_level,
                str(outside_state.close_vehicle),
                str(min(outside_state.close_vehicle_count, 2)),
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _row_to_event(self, row: sqlite3.Row) -> dict:
        reasons = []
        try:
            reasons = json.loads(row["reasons_json"]) if row["reasons_json"] else []
        except json.JSONDecodeError:
            reasons = []

        inside_snapshot = row["inside_snapshot"] or ""
        outside_snapshot = row["outside_snapshot"] or ""

        row_keys = row.keys() if hasattr(row, "keys") else []
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "risk_level": row["risk_level"],
            "risk_score": row["risk_score"],
            "category": row["category"] if "category" in row_keys else "Normal Driving",
            "confidence": float(row["confidence"]) if "confidence" in row_keys else 1.0,
            "inside_status": row["inside_status"],
            "outside_traffic": row["outside_traffic"],
            "reasons": reasons,
            "inside_snapshot_url": self._snapshot_url(inside_snapshot),
            "outside_snapshot_url": self._snapshot_url(outside_snapshot),
        }

    def export_csv(
        self,
        risk_level: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> str:
        events = self.fetch_events(limit=5000, risk_level=risk_level, category=category, search=search)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Event ID",
            "Timestamp",
            "Risk Level",
            "Risk Score",
            "Category",
            "Confidence",
            "Inside Status",
            "Outside Traffic",
            "Reasons",
        ])
        for event in events:
            writer.writerow([
                event["id"],
                event["created_at"],
                event["risk_level"],
                event["risk_score"],
                event.get("category", "Normal Driving"),
                event.get("confidence", 1.0),
                event["inside_status"],
                event["outside_traffic"],
                " | ".join(event.get("reasons", [])),
            ])
        return output.getvalue()

    @staticmethod
    def _placeholder_snapshot() -> str:
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 360'>"
            "<rect width='640' height='360' fill='#dce5f2'/>"
            "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' "
            "fill='#6e7f95' font-family='Segoe UI, Arial' font-size='24'>No snapshot</text>"
            "</svg>"
        )
        return f"data:image/svg+xml;utf8,{quote(svg)}"

    def _snapshot_url(self, snapshot_name: str) -> str:
        if not snapshot_name:
            return self._placeholder_snapshot()
        snapshot_path = self.settings.snapshot_dir / snapshot_name
        if not snapshot_path.exists():
            return self._placeholder_snapshot()
        return f"/events-media/{Path(snapshot_name).name}"
