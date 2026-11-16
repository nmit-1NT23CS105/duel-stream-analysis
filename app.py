"""
Dual-Stream Safety Hub - Cloud & Hugging Face Entrypoint
Serves complete custom FastAPI dashboard, analytics, and incident review on port 7860.
"""
import os
import uvicorn
from app.main import app

try:
    import gradio as gr
    demo = gr.Blocks(title="Dual-Stream Driving Safety Hub")
    app = gr.mount_gradio_app(app, demo, path="/gradio")
except Exception:
    pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
