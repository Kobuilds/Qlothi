from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from io import BytesIO
from PIL import Image
from ultralytics import YOLO

app = FastAPI(title="Qlothi Backend")

# Enable CORS so the Chrome extension can make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the YOLOv8 segmentation model on startup
print("Loading YOLOv8 segmentation model...")
model = YOLO('yolov8n-seg.pt')
print("Model loaded.")

import base64

class AnalyzeRequest(BaseModel):
    base64_image: str

@app.post("/analyze")
async def analyze_outfit(request: AnalyzeRequest):
    print(f"Received request with base64 image of length: {len(request.base64_image)}")
    
    try:
        # 1. Decode base64 into PIL Image
        print("1. Decoding base64 image data...")
        # Strip potential data URI scheme header if it exists
        base64_data = request.base64_image
        if base64_data.startswith('data:image'):
            base64_data = base64_data.split(',')[1]
            
        image_bytes = base64.b64decode(base64_data)
        
        # 2. Open with PIL
        print("2. Opening image with PIL...")
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = img.size
        print(f"Image opened: {width}x{height}")
        
        # 3. Run YOLO segmentation
        print("3. Running YOLO segmentation model...")
        results = model.predict(source=img, save=False, conf=0.25)
        print("YOLO processing complete.")
        
        # 4. Extract results
        print("4. Extracting masks and bounding boxes...")
        items = []
        result = results[0]
        
        if result.masks is not None:
            # Result contains boxes, masks, etc.
            boxes = result.boxes
            masks = result.masks.xyn # Normalized polygon coordinates
            
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                confidence = float(boxes.conf[i].item())
                class_name = model.names[cls_id]
                
                polygon = masks[i].tolist()
                bbox_normalized = boxes.xyxyn[i].tolist() # Normalized format for frontend scaling
                
                if class_name == 'person' and len(polygon) > 0:
                    import cv2
                    import numpy as np
                    
                    # Heuristic: split person mask into Upper and Lower clothes for the PoC
                    # Convert normalized polygon back to arbitrary pixel scale (e.g., 1000x1000) for reliable splitting
                    scale = 1000
                    poly_pts = np.array([[int(p[0] * scale), int(p[1] * scale)] for p in polygon], dtype=np.int32)
                    
                    min_y = np.min(poly_pts[:, 1])
                    max_y = np.max(poly_pts[:, 1])
                    mid_y = int(min_y + (max_y - min_y) * 0.45) # Upper 45% is top, lower 55% is bottom
                    
                    # Create blank binary masks
                    mask_upper = np.zeros((scale, scale), dtype=np.uint8)
                    mask_lower = np.zeros((scale, scale), dtype=np.uint8)
                    
                    # Fill the whole person polygon on both masks
                    cv2.fillPoly(mask_upper, [poly_pts], 255)
                    cv2.fillPoly(mask_lower, [poly_pts], 255)
                    
                    # Erase bottom part from upper mask
                    cv2.rectangle(mask_upper, (0, mid_y), (scale, scale), 0, -1)
                    # Erase top part from lower mask
                    cv2.rectangle(mask_lower, (0, 0), (scale, mid_y), 0, -1)
                    
                    # Find contours of the remaining shapes
                    contours_upper, _ = cv2.findContours(mask_upper, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    contours_lower, _ = cv2.findContours(mask_lower, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    if contours_upper:
                        largest_upper = max(contours_upper, key=cv2.contourArea)
                        upper_poly_norm = [[float(pt[0][0])/scale, float(pt[0][1])/scale] for pt in largest_upper]
                        if len(upper_poly_norm) > 3:
                            items.append({
                                "id": f"item_{i}_upper",
                                "class_name": "upper-clothes",
                                "confidence": confidence,
                                "polygon_normalized": upper_poly_norm,
                                "bbox_normalized": bbox_normalized
                            })
                            
                    if contours_lower:
                        largest_lower = max(contours_lower, key=cv2.contourArea)
                        lower_poly_norm = [[float(pt[0][0])/scale, float(pt[0][1])/scale] for pt in largest_lower]
                        if len(lower_poly_norm) > 3:
                            items.append({
                                "id": f"item_{i}_lower",
                                "class_name": "lower-clothes",
                                "confidence": confidence,
                                "polygon_normalized": lower_poly_norm,
                                "bbox_normalized": bbox_normalized
                            })
                else:
                    items.append({
                        "id": f"item_{i}",
                        "class_name": class_name,
                        "confidence": confidence,
                        "polygon_normalized": polygon,
                        "bbox_normalized": bbox_normalized
                    })
        
        print(f"Successfully extracted {len(items)} items.")
        return {
            "status": "success",
            "message": f"Processed image. Found {len(items)} items.",
            "image_size": {"width": width, "height": height},
            "items": items
        }
        
    except Exception as e:
        print(f"CRITICAL ERROR processing image: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Backend Error: {str(e)}",
            "items": []
        }

@app.get("/")
async def root():
    return {"message": "Qlothi API is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
