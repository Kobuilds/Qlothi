FROM python:3.11-slim

WORKDIR /app

# System libs opencv-python-headless still links against
RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 \
      libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

# CPU-only PyTorch — HF Spaces free tier has no GPU and the CUDA wheels are ~4GB
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download the Segformer weights at build time so cold starts don't stall on a 350MB download
RUN python -c "from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation; SegformerImageProcessor.from_pretrained('mattmdjaga/segformer_b2_clothes'); AutoModelForSemanticSegmentation.from_pretrained('mattmdjaga/segformer_b2_clothes')"

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
