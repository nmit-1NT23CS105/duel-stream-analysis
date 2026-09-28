# Phase 2 Plan: Advanced Dangerous Driving Detection

## 1. Phase 2 Goal

Phase 1 proved that the core dual-stream idea is feasible:

- inside-cabin monitoring works
- outside-road monitoring works
- live and recorded modes work
- rule-based fusion works
- dashboard integration works

Phase 2 should move the project from a **working PoC** to a **more reliable, feature-rich, and evaluable intelligent safety system**.

The main Phase 2 goal is:

**Improve detection reliability, add richer dangerous-driving features, strengthen fusion logic, enable event logging, and create a proper evaluation workflow.**

---

## 2. Phase 2 Objectives

1. Improve the robustness of the current inside and outside monitoring modules.
2. Add more dangerous-driving features beyond basic drowsiness and vehicle counting.
3. Upgrade the current rule-based fusion into a stronger confidence-aware temporal fusion system.
4. Add event logging, alert history, and evidence storage.
5. Prevent common user errors such as swapped inside/outside video uploads.
6. Add explainable reasoning for final risk output.
7. Introduce a formal evaluation workflow using defined scenarios and datasets.

---

## 3. Phase 2 Scope

Phase 2 should still remain practical and modular. It does not need to become a full production-grade automotive platform yet.

Phase 2 will focus on:

- stronger logic
- richer features
- better reliability
- better user safety feedback
- proper testing support

Phase 2 will not yet fully require:

- complete embedded deployment
- fleet-scale cloud architecture
- certified automotive-grade safety pipeline
- fully trained custom deep models from scratch for every module

---

## 4. Advanced Features To Build

### 4.1 Inside Monitoring Upgrades

- stronger distraction logic using head orientation persistence
- repeated-yawn pattern detection
- fatigue escalation from combined EAR, MAR, and attention cues
- phone usage detection
- seatbelt detection
- better handling for glasses, side-face, and low-confidence face states
- confidence score for inside predictions

### 4.2 Outside Monitoring Upgrades

- lane-presence or lane-drift awareness
- stronger close-vehicle logic
- better traffic density scoring
- improved filtering for false vehicle detections
- optional speed-trend approximation from bounding box motion
- confidence score for outside predictions

### 4.3 Fusion Upgrades

- confidence-aware fusion
- dynamic weighting of inside vs outside streams
- temporal reasoning across time windows
- escalation for persistent dangerous states
- stronger combination rules
- explainable risk reasoning

### 4.4 Dashboard Upgrades

- real event history
- event cards with timestamp and risk reason
- snapshots/evidence preview
- current confidence indicators
- richer fused reasoning display
- better upload validation messages

---

## 5. Advanced Logic To Add

### 5.1 Input Validation Logic

Current issue:
- inside and outside videos can be uploaded into the wrong slots

Phase 2 solution:
- inspect the first `20-50` frames of uploaded videos
- if face presence is high and road/vehicle presence is low, classify as likely inside video
- if vehicle/road presence is high and face presence is low, classify as likely outside video
- warn the user if the streams appear swapped
- optionally allow a one-click "Swap Streams" correction

### 5.2 Confidence-Aware Inside Logic

Add confidence scoring based on:

- face visibility
- pose quality
- landmark reliability
- number of stable frames
- consistency of EAR/MAR trends

If confidence is low:
- avoid overconfident risky classification
- downgrade to `Monitoring` or `Low confidence`

### 5.3 Confidence-Aware Outside Logic

Add confidence scoring based on:

- number of confirmed tracks
- box size quality
- edge proximity
- repeated detections across frames
- scene stability

If confidence is low:
- reduce contribution to final fusion score

### 5.4 Temporal Reasoning

Instead of reacting mainly to instant frame-level conditions, use a temporal window such as:

- last `3-5` seconds of inside behavior
- last `3-5` seconds of outside behavior
- persistence counters for risky combinations

Examples:

- repeated yawns over time increase fatigue probability
- prolonged distraction is riskier than one brief head turn
- sustained close-vehicle presence is riskier than one passing frame

### 5.5 Dynamic Fusion Weights

Current fusion is fixed rule-based scoring.

Phase 2 should use:

- higher inside weight when driver confidence is high
- lower inside weight when face visibility is poor
- higher outside weight in dense traffic
- higher combination penalty when both streams indicate danger together

### 5.6 Priority Event Escalation

Certain combinations should trigger immediate stronger risk escalation:

- `Fatigue Risk + close vehicle`
- `Distracted + heavy traffic`
- `No Face + active traffic`
- `Phone usage + close vehicle`
- `Seatbelt missing + active driving`

### 5.7 Explainable Fusion Reasons

Every high or critical fused result should expose structured reasons like:

- driver eyes remained closed for multiple frames
- repeated yawning detected
- close vehicle detected ahead
- traffic density is high
- combined driver and road danger elevated final risk

This can be shown in the dashboard and stored in the event log.

---

## 6. Phase 2 Functional Requirements

### FR10: Input Type Validation
- The system shall validate whether uploaded inside/outside streams appear to match their intended scene type.

### FR11: Phone Usage Detection
- The system shall detect likely phone usage in the inside-cabin stream.

### FR12: Seatbelt Detection
- The system shall detect whether a visible driver appears to be wearing a seatbelt.

### FR13: Advanced Fatigue Logic
- The system shall use repeated yawns, prolonged low EAR, and attention weakness to escalate fatigue risk.

### FR14: Lane/Road Structure Awareness
- The system shall include basic lane-presence or lane-deviation cues in the outside stream.

### FR15: Confidence-Aware Fusion
- The system shall weight inside and outside risk contributions according to prediction confidence.

### FR16: Temporal Fusion
- The system shall use short-term time windows and persistence logic for fused risk generation.

### FR17: Event Logging
- The system shall store high-risk and critical events with timestamp, level, reasons, and optional snapshots.

### FR18: Explainable Risk Output
- The system shall display structured reasons behind the current fused risk output.

### FR19: Upload Safeguards
- The system shall warn the user when uploads are invalid, oversized, or likely swapped.

### FR20: Evaluation Support
- The system shall support testing using defined scenarios, labeled clips, and module-wise result recording.

---

## 7. Phase 2 Non-Functional Requirements

- Maintain near real-time operation on the same development environment where possible.
- Keep the system modular so new modules can be added without large rewrites.
- Improve fault tolerance for missing streams or poor detections.
- Ensure recorded-mode workflows remain simple for demo and evaluation use.
- Keep the dashboard understandable and not overloaded with technical detail.
- Make the fusion output more transparent and explainable.
- Preserve Windows-friendly setup and sharing workflow.

---

## 8. Codebase Areas To Extend

### `app/models/inside_monitor.py`
Add:

- phone usage logic
- seatbelt-related inference or detection hooks
- stronger fatigue accumulation
- confidence scoring
- better temporal tracking of attention behavior

### `app/models/outside_monitor.py`
Add:

- lane/road structure estimation
- better close-vehicle confidence
- track quality scoring
- richer traffic-risk metrics

### `app/fusion/risk_engine.py`
Add:

- confidence-aware scoring
- dynamic weighting
- temporal windows
- priority event escalation
- structured explanation outputs

### `app/services/system_service.py`
Add:

- upload validation
- stream scene-type checking
- stronger event handling
- optional background validation before applying recorded mode

### `app/storage/event_store.py`
Replace the current disabled stub with:

- event persistence
- recent history fetch
- event filtering by risk level
- optional snapshot path storage

### `app/static/index.html`
Add:

- confidence indicators
- event list area
- upload validation messages
- richer reasoning panel

### `app/static/app.js`
Add:

- display of event history
- upload warnings
- confidence indicators
- better risk explanation rendering

---

## 9. Recommended Phase 2 Build Order

### Step 1: Safety and Usability Fixes
- input validation for swapped videos
- upload size/type checks
- stronger recorded-mode validation

### Step 2: Event Logging
- enable real event history
- save level, timestamp, reasons
- add optional inside/outside snapshots

### Step 3: Inside Behavior Expansion
- phone usage detection
- seatbelt detection
- stronger fatigue accumulation

### Step 4: Outside Behavior Expansion
- lane awareness
- richer road-risk scoring
- improved close-vehicle logic

### Step 5: Fusion Upgrade
- confidence scoring
- dynamic weights
- temporal fusion
- priority escalation rules

### Step 6: Explainability
- structured explanation reasons
- dashboard reasoning cards
- explainable event summaries

### Step 7: Evaluation Workflow
- define test scenarios
- create labeled clips
- module-wise observations
- final fused-risk validation

---

## 10. Data and Dataset Requirements For Phase 2

Phase 2 should begin with a small but structured validation setup.

### Recommended data sources
- custom recorded inside-cabin videos
- custom recorded outside-road videos
- synchronized paired demo clips where possible
- selected public datasets for support, if approved later

### Recommended scenario categories

Inside scenarios:
- normal driving
- yawning
- prolonged eye closure
- distraction
- phone usage
- no-face/partial-face cases

Outside scenarios:
- low traffic
- medium traffic
- high traffic
- close front vehicle
- lane change or drift scenes
- stopped traffic scenes

Combined scenarios:
- alert driver + low traffic
- fatigued driver + low traffic
- distracted driver + high traffic
- phone usage + close vehicle
- no-face + active road scene

### Ground-truth labels to record
- inside status
- outside status
- presence of close vehicle
- traffic level
- final expected risk level

---

## 11. Evaluation Plan For Phase 2

Phase 2 should avoid unsupported global accuracy claims.

Instead evaluate:

### Inside module
- face presence success
- drowsiness detection behavior
- yawn detection behavior
- distraction detection behavior
- phone usage detection behavior
- seatbelt detection behavior

### Outside module
- vehicle detection consistency
- track stability
- close-vehicle behavior
- traffic-level correctness
- lane-related cue quality

### Fusion module
- whether final risk matches labeled scenario expectation
- whether high-risk events are triggered appropriately
- whether explanations are consistent with inputs

### Runtime
- approximate FPS in live and recorded modes
- behavior under longer session runs

---

## 12. Acceptance Criteria For Phase 2

Phase 2 can be considered complete if:

- swapped input validation is working
- event history is enabled and searchable
- phone detection is working in at least prototype form
- seatbelt detection is working in at least prototype form
- fusion uses confidence-aware and temporal reasoning
- dashboard shows clearer reasons for risk
- a labeled evaluation workflow exists
- the system remains usable in live and recorded modes

---

## 13. Risks and Challenges

- phone and seatbelt detection may need extra data or model support
- lane-awareness may require careful scope control to stay practical
- stronger fusion logic can reduce false positives but may increase complexity
- event logging with snapshots needs storage management
- larger feature set may reduce FPS if not tuned carefully

---

## 14. Suggested Phase 2 Deliverables

- upgraded backend logic
- improved dashboard with explanations and events
- event storage implementation
- input-validation pipeline
- richer fusion engine
- evaluation notes with scenario-based observations
- updated PPT and report material for next review

---

## 15. Best Phase 2 Summary

Phase 2 should transform the current system from a basic dual-stream PoC into a more reliable dangerous-driving intelligence platform by adding stronger behavior detection, confidence-aware temporal fusion, event logging, explainable reasoning, and structured evaluation support.
