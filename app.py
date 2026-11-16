"""
Dual-Stream Safety Hub - Cloud & Hugging Face Entrypoint
Serves complete custom FastAPI dashboard, analytics, and incident review on port 7860.
Includes ZeroGPU integration and Gradio UI wrapper for Hugging Face Spaces.
"""
import os
import uvicorn
from app.main import app

# Hugging Face ZeroGPU compatibility
try:
    import spaces

    @spaces.GPU
    def zero_gpu_handler(text: str = "") -> str:
        """Hugging Face ZeroGPU worker function."""
        return "ZeroGPU Ready"
except Exception:
    def zero_gpu_handler(text: str = "") -> str:
        return "CPU Ready"

try:
    import gradio as gr

    with gr.Blocks(title="Dual-Stream Driving Safety Hub") as demo:
        # ZeroGPU event listener for startup check scanner
        dummy_input = gr.Textbox(value="ping", visible=False)
        dummy_output = gr.Textbox(visible=False)
        dummy_btn = gr.Button("Init", visible=False)
        dummy_btn.click(zero_gpu_handler, inputs=dummy_input, outputs=dummy_output)

        gr.HTML("""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 24px 16px;">
            <div style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 6px 14px; border-radius: 9999px; font-weight: 600; font-size: 13px; margin-bottom: 12px;">
                🛡️ AI Dangerous Driving Detection Hub • Live Deployment
            </div>
            <h1 style="color: #0f172a; font-size: 26px; font-weight: 800; margin: 0 0 10px 0;">Dual-Stream Road & Cabin Safety AI</h1>
            <p style="color: #64748b; font-size: 15px; max-width: 650px; margin: 0 auto 20px auto;">
                Real-time inside driver monitoring (microsleep, distraction, gaze, stress) and outside road risk detection (TTC collision, VRU pedestrians/cyclists, traffic signals).
            </p>
            <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-bottom: 24px;">
                <a href="/" target="_blank" style="background: #2563eb; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">🚀 Open Fullscreen Dashboard</a>
                <a href="/analytics" target="_blank" style="background: #0f172a; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">📊 System Analytics</a>
                <a href="/incidents" target="_blank" style="background: #475569; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">🚨 Incident Log</a>
                <a href="/mobile" target="_blank" style="background: #16a34a; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">📱 Mobile Driver View</a>
            </div>
            <div style="width: 100%; max-width: 1280px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08);">
                <iframe src="/" style="width: 100%; height: 860px; border: none; display: block;"></iframe>
            </div>
        </div>
        """)

    app = gr.mount_gradio_app(app, demo, path="/hub")
except Exception as e:
    print(f"[Warning] Gradio mount skipped: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
