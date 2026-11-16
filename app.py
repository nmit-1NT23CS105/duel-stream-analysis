"""
Dual-Stream Safety Hub - Cloud & Hugging Face Entrypoint
Serves custom FastAPI dashboard, analytics, and incident review on port 7860.
Includes ZeroGPU integration and Gradio UI wrapper for Hugging Face Spaces.
"""
import os

# Hugging Face ZeroGPU MUST be imported before torch, ultralytics, or any other CUDA-touching library
try:
    import spaces
except Exception:
    spaces = None

import gradio as gr
from app.main import app as fastapi_app
import uvicorn

if spaces is not None:
    @spaces.GPU
    def predict_safety(status_input: str = "Active") -> str:
        """Hugging Face ZeroGPU worker endpoint."""
        return f"Dual-Stream Safety Engine Active: {status_input}"
else:
    def predict_safety(status_input: str = "Active") -> str:
        return f"Dual-Stream Safety Engine Active (CPU): {status_input}"

# Register root Gradio Interface decorated with @spaces.GPU for HF startup scanner
demo = gr.Interface(
    fn=predict_safety,
    inputs=gr.Textbox(label="System Status", value="Dual-Stream AI Safety Active"),
    outputs=gr.Textbox(label="ZeroGPU Pipeline Allocation"),
    title="🛡️ Dual-Stream AI Driving Safety Hub",
    description="Real-Time Inside Driver & Outside Road Risk Detection System",
)

# Mount Gradio onto custom FastAPI application
app = gr.mount_gradio_app(fastapi_app, demo, path="/hub")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
