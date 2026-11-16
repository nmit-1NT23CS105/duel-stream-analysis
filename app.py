"""
Dual-Stream Safety Hub - Cloud & Hugging Face Entrypoint
Serves custom FastAPI dashboard, analytics, and incident review on port 7860.
Includes ZeroGPU integration and Gradio UI wrapper for Hugging Face Spaces.
"""
import os
import time

# Hugging Face ZeroGPU MUST be imported before torch, ultralytics, or any other CUDA-touching library
try:
    import spaces
except Exception:
    spaces = None

import gradio as gr
from app.main import app as fastapi_app
from starlette.staticfiles import StaticFiles

if spaces is not None:
    @spaces.GPU
    def predict_safety(status_input: str = "Active") -> str:
        """Hugging Face ZeroGPU worker endpoint."""
        return f"Dual-Stream AI Safety ZeroGPU Active: {status_input}"
else:
    def predict_safety(status_input: str = "Active") -> str:
        return f"Dual-Stream AI Safety Active: {status_input}"

with gr.Blocks(title="Dual-Stream Driving Safety AI Hub") as demo:
    gr.HTML("""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 20px 10px;">
        <div style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 6px 14px; border-radius: 9999px; font-weight: 600; font-size: 13px; margin-bottom: 12px;">
            🛡️ AI Dangerous Driving Detection Hub • Live Cloud Deployment
        </div>
        <h1 style="color: #0f172a; font-size: 26px; font-weight: 800; margin: 0 0 10px 0;">Dual-Stream Road & Cabin Safety AI</h1>
        <p style="color: #64748b; font-size: 15px; max-width: 650px; margin: 0 auto 20px auto;">
            Real-time inside driver monitoring (microsleep, distraction, gaze, stress) and outside road hazard detection (TTC collision, VRU pedestrians/cyclists, traffic signals).
        </p>
        <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-bottom: 20px;">
            <a href="/dashboard" target="_blank" style="background: #2563eb; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">🚀 Open Fullscreen Dashboard</a>
            <a href="/analytics" target="_blank" style="background: #0f172a; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">📊 System Analytics</a>
            <a href="/incidents" target="_blank" style="background: #475569; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">🚨 Incident Log</a>
            <a href="/mobile" target="_blank" style="background: #16a34a; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">📱 Mobile Driver View</a>
        </div>
    </div>
    """)

    with gr.Row():
        inp = gr.Textbox(label="Telemetry Channel", value="Driver Attention & Road Stream Active", scale=4)
        btn = gr.Button("Evaluate Stream State", variant="primary", scale=1)
    out = gr.Textbox(label="Fused Risk Assessment Result")
    btn.click(predict_safety, inputs=inp, outputs=out)

    gr.HTML("""
    <div style="width: 100%; max-width: 1300px; margin: 20px auto 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <iframe src="/dashboard" style="width: 100%; height: 860px; border: none; display: block;"></iframe>
    </div>
    """)

demo.queue()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app_instance, _, _ = demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        prevent_thread_lock=True
    )

    # Mount custom FastAPI dashboard and API routes directly onto Gradio ASGI app
    app_instance.mount("/dashboard", fastapi_app)
    app_instance.include_router(fastapi_app.router)
    app_instance.mount("/static", StaticFiles(directory="app/static"), name="custom_static")
    app_instance.mount("/data", StaticFiles(directory="data"), name="custom_data")

    # Keep server process active
    while True:
        time.sleep(3600)
