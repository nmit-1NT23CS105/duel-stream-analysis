FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/home/user/app/data/ultralytics

# Install system libraries required by OpenCV, MediaPipe, and YOLO
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up user with UID 1000 (standard for Hugging Face Spaces Docker SDK)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app

# Install lightweight PyTorch CPU wheel first for ultra-fast build
RUN pip install --no-cache-dir --user torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install remaining python packages
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy application files
COPY --chown=user:user . .

# Ensure data directories exist and pre-cache YOLO weights for instant startup
RUN mkdir -p data/uploads data/events/media data/ultralytics && \
    python -c "from ultralytics import YOLO; YOLO('yolov8s.pt'); YOLO('yolov8n.pt')"

# Expose port 7860 (Hugging Face default)
EXPOSE 7860

# Start FastAPI server directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
