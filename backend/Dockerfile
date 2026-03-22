FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory
WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install CPU PyTorch to avoid massive ~4GB CUDA dependencies that aren't needed on free tier Spaces
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies (including transformers, FastAPI, Playwright)
RUN pip install --no-cache-dir -r requirements.txt

# Pre-install the Playwright Chromium binary required for Google Lens scraping
RUN playwright install chromium

# Copy the actual application files
COPY . .

# Pre-download the HuggingFace Segformer AI model. By doing this during the build phase, 
# the server will start up instantly instead of halting to download a 350MB file on every reboot.
RUN python -c "from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation; SegformerImageProcessor.from_pretrained('mattmdjaga/segformer_b2_clothes'); AutoModelForSemanticSegmentation.from_pretrained('mattmdjaga/segformer_b2_clothes')"

# Hugging Face Spaces exposes port 7860 by default
EXPOSE 7860

# Start the FastAPI server using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
