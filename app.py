"""
Dual-Stream Safety Hub - Hugging Face Cloud Deployment Entrypoint
Uses Gradio 6 Server Mode (FastAPI) with native ZeroGPU acceleration.
Serves the full custom dashboard, video streams, analytics, and mobile UI.
"""
from pathlib import Path
import os

try:
    import spaces
except Exception:
    spaces = None

from gradio import Server
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.main import app as main_fastapi_app, service

# Ensure backend processing service is running
if not service.state.started:
    service.start()

# 1. Initialize Gradio Server (inherits directly from FastAPI)
app = Server(title="Dual-Stream Safety Hub")

# 2. Attach all application routes (APIs, live MJPEG streaming, WebSocket, uploads)
app.include_router(main_fastapi_app.router)

# 3. Mount static and media assets
root_dir = Path(__file__).resolve().parent
static_dir = root_dir / "app" / "static"
media_dir = root_dir / "data" / "events" / "media"
media_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/events-media", StaticFiles(directory=media_dir), name="events-media")

# 4. ZeroGPU allocation hook
if spaces is not None:
    @spaces.GPU
    def run_safety_eval(telemetry: str = "Active") -> str:
        return f"ZeroGPU Pipeline Active: {telemetry}"
    app.api(name="predict")(run_safety_eval)
else:
    def run_safety_eval(telemetry: str = "Active") -> str:
        return f"CPU Pipeline Active: {telemetry}"
    app.api(name="predict")(run_safety_eval)

# 5. Serve custom frontend pages directly
@app.get("/")
async def root_index():
    return FileResponse(static_dir / "index.html")

@app.get("/incidents")
async def root_incidents():
    return FileResponse(static_dir / "incidents.html")

@app.get("/analytics")
async def root_analytics():
    return FileResponse(static_dir / "analytics.html")

@app.get("/mobile")
async def root_mobile():
    return FileResponse(static_dir / "mobile" / "index.html")

if __name__ == "__main__":
    app.launch()
