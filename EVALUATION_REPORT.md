# Dual-Stream Dangerous Driving Detection: Evaluation & Benchmark Report

Generated automatically via `evaluate.py` (Phase 2 FR20).

- **Total Scenarios**: 7
- **Overall Risk Accuracy**: 100.0%
- **Evaluation Timestamp**: 2026-09-28 13:53:33

## Scenario Evaluation Table

| Scenario | Expected Risk | Predicted Risk | Score | Status | Top Reason |
|---|---|---|---|---|---|
| S1: Alert Driver on Clear Road | Low | Low | 0 | Pass | Driver appears awake (EAR 0.32, attention 0.95) |
| S2: Fatigued Driver with Close Vehicle | Critical | Critical | 100 | Pass | Fatigue risk: EAR 0.14, MAR 0.68, attention 0.75 |
| S3: Distracted Driver during Lane Drift | High | High | 82 | Pass | Driver attention dropped (0.18) |
| S4: Handheld Phone Usage in Active Traffic | High | High | 60 | Pass | Possible handheld phone usage detected (0.82) |
| S5: Unfastened Seatbelt with Rapid Closing Vehicle | High | High | 78 | Pass | Driver appears awake (EAR 0.30, attention 0.90) |
| S6: Extreme Danger (Asleep + Rapid Closing Vehicle) | Critical | Critical | 100 | Pass | Low EAR detected (0.12) |
| S7: Unmarked Rural Road with Alert Driver | Low | Low | 8 | Pass | Driver appears awake (EAR 0.31, attention 0.92) |

## Confusion Matrix

| Actual \ Predicted | Low | Medium | High | Critical |
|---|---|---|---|---|
| **Low** | 2 | 0 | 0 | 0 |
| **Medium** | 0 | 0 | 0 | 0 |
| **High** | 0 | 0 | 3 | 0 |
| **Critical** | 0 | 0 | 0 | 2 |
