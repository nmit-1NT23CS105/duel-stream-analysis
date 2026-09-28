from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.services.system_service import DualStreamService


service = DualStreamService(settings)
static_dir = Path(__file__).parent / "static"


class InputConfigPayload(BaseModel):
    mode: str
    inside_source: str | None = None
    outside_source: str | None = None


class ControlPayload(BaseModel):
    action: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    service.start()
    try:
        yield
    except asyncio.CancelledError:
        # Uvicorn on Windows can cancel the lifespan task during Ctrl+C or reload.
        # Treat that as a normal shutdown so the app exits without a noisy traceback.
        pass
    finally:
        service.stop()


app = FastAPI(
    title="Dangerous Driving Detection - Phase 1",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/events-media", StaticFiles(directory=settings.snapshot_dir), name="events-media")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/incidents")
async def incidents_page() -> FileResponse:
    return FileResponse(static_dir / "incidents.html")


@app.get("/api/state")
async def get_state() -> JSONResponse:
    return JSONResponse(service.get_state())


@app.get("/api/input-config")
async def get_input_config() -> JSONResponse:
    return JSONResponse(service.get_input_config())


@app.post("/api/input-config")
async def update_input_config(payload: InputConfigPayload) -> JSONResponse:
    try:
        config = service.configure_inputs(
            mode=payload.mode,
            inside_source=payload.inside_source,
            outside_source=payload.outside_source,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"message": "Input mode updated", "config": config})


@app.get("/api/events")
async def get_events(
    limit: int = 8,
    risk_level: str | None = None,
    search: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        {
            "events": service.get_recent_events(
                limit=limit,
                risk_level=risk_level,
                search=search,
            )
        }
    )


@app.post("/api/upload/{stream_name}")
async def upload_recording(stream_name: str, request: Request, filename: str = "") -> JSONResponse:
    try:
        upload_result = await service.save_uploaded_recording_stream(
            stream_name=stream_name,
            filename=filename,
            stream=request.stream(),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"Upload failed: {str(exc)}"}, status_code=500)
    return JSONResponse(
        {
            "message": "Recording uploaded",
            "path": upload_result["path"],
            "stream": stream_name,
            "validation": upload_result["validation"],
            "bundle": upload_result["bundle"],
        }
    )


@app.post("/api/control")
async def control_processing(payload: ControlPayload) -> JSONResponse:
    action = payload.action.lower().strip()
    if action == "stop":
        config = service.pause_processing()
        return JSONResponse({"message": "Processing stopped", "config": config})
    if action == "start":
        config = service.resume_processing()
        return JSONResponse({"message": "Processing started", "config": config})
    return JSONResponse({"error": "Action must be 'start' or 'stop'."}, status_code=400)


@app.get("/stream/{stream_name}")
async def stream(stream_name: str):
    if stream_name not in {"inside", "outside"}:
        return PlainTextResponse("Invalid stream", status_code=404)
    return StreamingResponse(
        service.frame_stream(stream_name),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
