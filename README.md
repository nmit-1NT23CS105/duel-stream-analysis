# Phase 1: Dual-Stream Dangerous Driving Detection

This project implements Phase 1 of a real-time dangerous driving detection system using:

- an inside-cabin live stream for driver monitoring
- an outside-road live stream for vehicle monitoring
- a rule-based fusion engine for preliminary risk scoring
- a clean dashboard for live visualization and event review

## Phase 1 Features

- Dual live video capture from inside and outside sources
- Switchable `Live` and `Recorded` input modes
- Driver face and facial landmark detection
- Driver-state estimation using EAR, MAR, and head-attention cues
- Drowsiness, yawning, distraction, and fatigue-risk classification
- Vehicle detection using a pretrained YOLO model
- Stable tracked IDs with current vehicle counting
- GPU-ready outside model profiles: `speed`, `balanced`, `accuracy`
- Fused risk levels: `Low`, `Medium`, `High`, `Critical`
- Event logging with timestamps and snapshots
- Recorded video upload and automatic playback classification
- Recorded video file names and playback progress bars
- Stream status badges with separate health indicators

## Recommended Environment

- Windows 10/11
- Python 3.11
- NVIDIA GPU optional but recommended

## Setup

1. Create a virtual environment:

```powershell
C:\Users\katar\AppData\Local\Programs\Python\Python311\python.exe -m venv .venv
```

2. Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

4. Copy the environment template:

```powershell
Copy-Item .env.example .env
```

5. Set camera sources in `.env`:

- `INSIDE_SOURCE=0` for webcam 0
- `OUTSIDE_SOURCE=1` for webcam 1
- you can also use video file paths or RTSP URLs
- `OUTSIDE_PROFILE=balanced` is the recommended default on your GPU

## Using Live and Recorded Modes

- `Live mode`: enter webcam indexes like `0` and `1`, or RTSP URLs, then click `Apply`
- `Recorded mode`: upload one inside video, one outside video, or both from the dashboard, then click `Apply`
- Recorded videos automatically loop and continue classifying frame by frame; if only one video is provided, the other stream stays unavailable
- Recorded mode shows the selected file names and live playback progress for both streams
- Use `Stop` to pause live or recorded analysis, and `Start` to resume
- Each stream card shows its mode badge plus a health indicator: `Online`, `Paused`, or `Offline`

## Outside Model Profiles

- `speed`: fastest, uses `yolov8n`
- `balanced`: better detection quality, uses `yolov8s`
- `accuracy`: strongest thresholds and larger inference size, slower

## Run

```powershell
python -m uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000`

## Accuracy Note

This Phase 1 system is built around pretrained models and live heuristics. High accuracy depends on:

- camera placement
- lighting
- road scene quality
- frame rate
- custom threshold tuning
- your final evaluation dataset

Do not claim a blanket global `95%` accuracy unless you measure it on a clearly defined test set.

## Next Phases

- Phase 2: richer dangerous behavior logic and stronger temporal reasoning
- Phase 3: explainable AI, optimization, analytics, and presentation-ready productization
