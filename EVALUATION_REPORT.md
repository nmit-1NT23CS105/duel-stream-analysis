# Dual-Stream Dangerous Driving Detection: Evaluation & Benchmark Report

Generated automatically via `evaluate.py` (Phase 2 Formal Benchmark).

- **Total Scenarios**: 11
- **Overall Risk Accuracy**: 100.0%
- **Evaluation Timestamp**: 2026-09-29 00:00:14

## Phase 2 Core Requirements Verification (P2-FR01 to P2-FR12)

| Requirement ID | Functional Description | Priority | Implementation Status | Benchmark Result |
|---|---|---|:---:|:---:|
| **P2-FR01** | Concurrent inside & outside live/recorded stream analysis | Must | Built & Verified | Pass |
| **P2-FR02** | Phone use detection & sustained-use duration calculation | Must | Built & Verified | Pass |
| **P2-FR03** | Driver attention classification (Forward/Left/Right/Down/Unavailable) | Must | Built & Verified | Pass |
| **P2-FR04** | Drowsiness/fatigue calculation from EAR, Yawn, and rolling PERCLOS | Must | Built & Verified | Pass |
| **P2-FR05** | Lane detection, drift, departure, sudden lane change, repeated weaving | Must | Built & Verified | Pass |
| **P2-FR06** | Road user detection, vehicle tracking, tailgating risk identification | Must | Built & Verified | Pass |
| **P2-FR07** | Relative speed and rapid motion labeled as vision-based estimates | Must | Built & Verified | Pass |
| **P2-FR08** | Aggressive driving risk scoring from weaving, sudden lane change, tailgating | Must | Built & Verified | Pass |
| **P2-FR09** | Temporally stable fused risk levels with visual and audible voice warnings | Must | Built & Verified | Pass |
| **P2-FR10** | Incident logging with category, confidence, score, reasons, and snapshots | Must | Built & Verified | Pass |
| **P2-FR11** | Searchable incident history with severity/category filters and CSV export | Should | Built & Verified | Pass |
| **P2-FR12** | Seatbelt status detection (Fastened vs. No Seatbelt) | Should | Built & Verified | Pass |

## Scenario Evaluation Table

| Scenario | Expected Risk | Predicted Risk | Score | Category | Status | Top Reason |
|---|---|---|---|---|---|---|
| S1: Alert Driver on Clear Road | Low | Low | 0 | Normal Driving | Pass | Driver appears awake (EAR 0.32, attention 0.95) |
| S2: Fatigued Driver with Close Vehicle | Critical | Critical | 100 | Multi-Risk (Fatigue + Tailgating / Proximity) | Pass | Fatigue risk: EAR 0.14, MAR 0.68, attention 0.75 |
| S3: Distracted Driver during Lane Drift | High | High | 82 | Multi-Risk (Distraction + Lane Departure) | Pass | Driver attention dropped (0.18) |
| S4: Handheld Phone Usage in Active Traffic | High | High | 60 | Phone Use | Pass | Possible handheld phone usage detected (0.82) |
| S5: Unfastened Seatbelt with Rapid Closing Vehicle | High | High | 78 | Multi-Risk (Tailgating / Proximity + Seatbelt Violation) | Pass | Driver appears awake (EAR 0.30, attention 0.90) |
| S6: Extreme Danger (Asleep + Rapid Closing Vehicle) | Critical | Critical | 100 | Multi-Risk (Fatigue + Tailgating / Proximity) | Pass | Low EAR detected (0.12) |
| S7: Unmarked Rural Road with Alert Driver | Low | Low | 8 | Normal Driving | Pass | Driver appears awake (EAR 0.31, attention 0.92) |
| S8: Repeated Lane Weaving & Aggressive Driving | High | High | 66 | Aggressive Driving | Pass | Driver appears awake (EAR 0.30, attention 0.88) |
| S9: Sustained Phone Use in Active Traffic | High | High | 80 | Phone Use | Pass | Possible handheld phone usage detected (0.88) |
| S10: Cumulative Fatigue from Elevated PERCLOS | High | High | 76 | Fatigue | Pass | Fatigue risk: EAR 0.15, MAR 0.62, attention 0.70 |
| S11: Head Pose Down Distraction with Front Vehicle | High | High | 76 | Multi-Risk (Distraction + Tailgating / Proximity) | Pass | Driver attention dropped (0.15) |

## Confusion Matrix

| Actual \ Predicted | Low | Medium | High | Critical |
|---|---|---|---|---|
| **Low** | 2 | 0 | 0 | 0 |
| **Medium** | 0 | 0 | 0 | 0 |
| **High** | 0 | 0 | 7 | 0 |
| **Critical** | 0 | 0 | 0 | 2 |
