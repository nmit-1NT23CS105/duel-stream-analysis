"""
Dual-Stream Safety Hub - Cloud & Hugging Face Entrypoint
Serves complete custom FastAPI dashboard, analytics, and incident review on port 7860.
"""
import os
import uvicorn
from app.main import app

# Hugging Face ZeroGPU compatibility
try:
    import spaces

    @spaces.GPU(duration=60)
    def zero_gpu_pipeline():
        """Keep Hugging Face ZeroGPU allocator active."""
        return True
except Exception:
    pass

try:
    import gradio as gr
    demo = gr.Blocks(title="Dual-Stream Driving Safety Hub")
    app = gr.mount_gradio_app(app, demo, path="/gradio")
except Exception:
    pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
