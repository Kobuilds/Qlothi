import requests
from io import BytesIO
from PIL import Image
from ultralytics import YOLO
import sys
import traceback

print("Testing YOLO and Image Download...")

try:
    print("Loading model...")
    model = YOLO('yolov8n-seg.pt')
    
    test_url = "https://i.pinimg.com/736x/87/1b/ad/871bada3666b61cdab572d4baeaed42e.jpg"
    print(f"Downloading from: {test_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.pinterest.com/'
    }
    response = requests.get(test_url, headers=headers, timeout=10)
    response.raise_for_status()
    print("Downloaded successfully.")
    
    img = Image.open(BytesIO(response.content)).convert("RGB")
    print(f"Image parsed. Size: {img.size}")
    
    results = model.predict(source=img, save=False, conf=0.25)
    print("YOLO finished predicting.")
    print(len(results[0].boxes), "objects found.")
    
except Exception as e:
    print(f"FAILED: {e}")
    traceback.print_exc()

print("Done testing.")
