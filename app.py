"""
Dual-Stream Safety Hub - Cloud & Hugging Face Entrypoint
Serves the full custom FastAPI dashboard, analytics, and incident review on port 7860.
ZeroGPU compatibility via mounted Gradio endpoint at /gradio.
"""
import os

# Hugging Face ZeroGPU MUST be imported before torch, ultralytics, or any other CUDA-touching library
try:
    import spaces
except Exception:
    spaces = None

from app.main import app as fastapi_app
import gradio as gr
import uvicorn

if spaces is not None:
    @spaces.GPU
    def predict_safety(status_input: str = "Active") -> str:
        """Hugging Face ZeroGPU worker endpoint."""
        return f"Dual-Stream AI Safety ZeroGPU Active: {status_input}"
else:
    def predict_safety(status_input: str = "Active") -> str:
        return f"Dual-Stream AI Safety Active: {status_input}"

# Register Gradio Blocks for Hugging Face ZeroGPU hardware scanner
with gr.Blocks(title="Dual-Stream Safety AI Backend") as demo:
    txt_input = gr.Textbox(label="Telemetry Signal", value="Driver & Road Stream Active")
    txt_output = gr.Textbox(label="ZeroGPU Allocation Status")
    btn = gr.Button("Ping GPU Worker", variant="primary")
    btn.click(fn=predict_safety, inputs=txt_input, outputs=txt_output)

demo.queue()

# Mount Gradio onto the custom FastAPI application at /gradio
# This leaves "/" as the full custom Driver Safety Dashboard!
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
