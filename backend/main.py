from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import base64
import numpy as np
import cv2
from io import BytesIO
from PIL import Image

app = FastAPI(title="Qlothi Backend")

# Enable CORS so the Chrome extension can make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the fashion segmentation model on startup
print("Loading Segformer fashion model (first run downloads ~350MB)...")
from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation
import torch

processor = SegformerImageProcessor.from_pretrained("mattmdjaga/segformer_b2_clothes")
fashion_model = AutoModelForSemanticSegmentation.from_pretrained("mattmdjaga/segformer_b2_clothes")
fashion_model.eval()
print("Fashion model loaded!")

# ATR label map produced by mattmdjaga/segformer_b2_clothes
LABEL_MAP = {
    0: "background", 1: "hat", 2: "hair", 3: "sunglasses",
    4: "upper-clothes", 5: "skirt", 6: "pants", 7: "dress",
    8: "belt", 9: "left-shoe", 10: "right-shoe", 11: "face",
    12: "left-leg", 13: "right-leg", 14: "left-arm", 15: "right-arm",
    16: "bag", 17: "scarf"
}

# Synthetic id: left-shoe (9) + right-shoe (10) are merged into one "Footwear" category
# so the user doesn't get two differently-labeled dots for one pair of shoes.
FOOTWEAR_CLASS = 100
SHOE_CLASSES = (9, 10)

# Classes the user can actually shop for.
SHOPPABLE_CLASSES = (1, 3, 4, 5, 6, 7, 8, FOOTWEAR_CLASS, 16, 17)

FRIENDLY_NAMES = {
    1: "Hat", 3: "Sunglasses", 4: "Top / Upper Wear",
    5: "Skirt", 6: "Pants", 7: "Dress", 8: "Belt",
    FOOTWEAR_CLASS: "Footwear",
    16: "Bag", 17: "Scarf / Accessory"
}

# Small accessories otherwise get dropped on full-body pins where they occupy very little area.
SMALL_ITEM_CLASSES = {1, 3, 8}  # hat, sunglasses, belt
MIN_AREA_PCT_DEFAULT = 0.005
MIN_AREA_PCT_SMALL = 0.001
# Contours smaller than this fraction of the largest contour for the same class are treated as fragments.
CONTOUR_KEEP_RATIO = 0.15

# Classes where the model routinely glues a top and a skirt into one region (or one drape-plus-skirt region).
# For these we try a vertical color split before emitting items.
SPLIT_CANDIDATE_CLASSES = {4, 5, 7}  # upper-clothes, skirt, dress
COLOR_SPLIT_MIN_AREA_PX = 2000     # don't bother on tiny regions
COLOR_SPLIT_KMEANS_SAMPLE = 10000  # cap clustering work on big masks
COLOR_DIST_MIN = 45                # RGB Euclidean below this = too similar to be two garments
MIN_CLUSTER_FRAC = 0.20            # each cluster must be ≥ this fraction of the region
VERTICAL_SEP_MIN = 1.0             # cluster-centroid y-gap vs. summed y-stddevs; < 1 = too overlapped


def _build_class_mask(seg_map: np.ndarray, class_id: int) -> np.ndarray:
    if class_id == FOOTWEAR_CLASS:
        combined = (seg_map == SHOE_CLASSES[0]) | (seg_map == SHOE_CLASSES[1])
        return combined.astype(np.uint8) * 255
    return (seg_map == class_id).astype(np.uint8) * 255


def _class_confidence(probs: np.ndarray, low_res_seg: np.ndarray, class_id: int) -> float:
    """Mean softmax score over pixels the model argmax-assigned to this class."""
    if class_id == FOOTWEAR_CLASS:
        mask = (low_res_seg == SHOE_CLASSES[0]) | (low_res_seg == SHOE_CLASSES[1])
        if not mask.any():
            return 0.0
        return float((probs[SHOE_CLASSES[0]] + probs[SHOE_CLASSES[1]])[mask].mean())
    mask = (low_res_seg == class_id)
    if not mask.any():
        return 0.0
    return float(probs[class_id][mask].mean())


def _try_vertical_color_split(cleaned_mask: np.ndarray, image_rgb: np.ndarray):
    """
    If the masked region contains two distinct colors stacked vertically
    (e.g. lavender top above a blue floral skirt both glued into one
    class), return (upper_mask, lower_mask). Otherwise return None.

    The checks are deliberately strict to avoid splitting single garments
    that just happen to have pattern variation or a belt.
    """
    mask_bool = cleaned_mask > 0
    n_pixels = int(mask_bool.sum())
    if n_pixels < COLOR_SPLIT_MIN_AREA_PX:
        return None

    coords = np.column_stack(np.where(mask_bool))  # (N, 2): [row, col]
    pixels = image_rgb[mask_bool].astype(np.float32)

    # Subsample for k-means so latency stays bounded on large masks.
    if n_pixels > COLOR_SPLIT_KMEANS_SAMPLE:
        idx = np.random.default_rng(0).choice(n_pixels, COLOR_SPLIT_KMEANS_SAMPLE, replace=False)
        sample = pixels[idx]
    else:
        sample = pixels

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, _, centers = cv2.kmeans(sample, 2, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

    # Reject when the two "clusters" are really the same color with noise.
    if np.linalg.norm(centers[0] - centers[1]) < COLOR_DIST_MIN:
        return None

    # Assign every masked pixel to its nearest center.
    dist0 = np.linalg.norm(pixels - centers[0], axis=1)
    dist1 = np.linalg.norm(pixels - centers[1], axis=1)
    labels = (dist1 < dist0).astype(np.int32)

    c0_count = int((labels == 0).sum())
    c1_count = int((labels == 1).sum())
    if min(c0_count, c1_count) < MIN_CLUSTER_FRAC * n_pixels:
        return None  # one color dominates — probably a single patterned garment

    y0 = coords[labels == 0, 0]
    y1 = coords[labels == 1, 0]
    y_gap = abs(float(y0.mean()) - float(y1.mean()))
    y_spread = float(y0.std()) + float(y1.std())
    if y_spread == 0 or (y_gap / y_spread) < VERTICAL_SEP_MIN:
        return None  # colors interleave vertically → pattern, not two stacked garments

    upper_label = 0 if y0.mean() < y1.mean() else 1

    upper_mask = np.zeros_like(cleaned_mask)
    lower_mask = np.zeros_like(cleaned_mask)
    upper_coords = coords[labels == upper_label]
    lower_coords = coords[labels != upper_label]
    upper_mask[upper_coords[:, 0], upper_coords[:, 1]] = 255
    lower_mask[lower_coords[:, 0], lower_coords[:, 1]] = 255

    # Clean up the halves — kmeans-on-pixels produces noisy edges.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    upper_mask = cv2.morphologyEx(upper_mask, cv2.MORPH_OPEN, kernel)
    upper_mask = cv2.morphologyEx(upper_mask, cv2.MORPH_CLOSE, kernel)
    lower_mask = cv2.morphologyEx(lower_mask, cv2.MORPH_OPEN, kernel)
    lower_mask = cv2.morphologyEx(lower_mask, cv2.MORPH_CLOSE, kernel)

    return upper_mask, lower_mask


def _contours_to_items(cleaned_mask: np.ndarray, class_id: int, width: int, height: int,
                       confidence: float, id_suffix: str = ""):
    contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []

    min_area_pct = MIN_AREA_PCT_SMALL if class_id in SMALL_ITEM_CLASSES else MIN_AREA_PCT_DEFAULT
    min_area_px = width * height * min_area_pct
    largest_area = max(cv2.contourArea(c) for c in contours)
    keep_floor = largest_area * CONTOUR_KEEP_RATIO

    items = []
    for idx, contour in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)):
        area = cv2.contourArea(contour)
        if area < min_area_px or area < keep_floor:
            continue

        epsilon = 0.005 * cv2.arcLength(contour, True)
        simplified = cv2.approxPolyDP(contour, epsilon, True)
        if len(simplified) < 4:
            continue

        polygon = [[float(pt[0][0]) / width, float(pt[0][1]) / height] for pt in simplified]
        px = [p[0] for p in polygon]
        py = [p[1] for p in polygon]
        bbox = [min(px), min(py), max(px), max(py)]

        items.append({
            "id": f"item_{class_id}_{id_suffix}{idx}",
            "class_name": FRIENDLY_NAMES.get(class_id, LABEL_MAP.get(class_id, "Item")),
            "confidence": round(confidence, 3),
            "polygon_normalized": polygon,
            "bbox_normalized": bbox,
            "area_pct": round(area / (width * height), 4),
        })
    return items


def _extract_items(class_mask: np.ndarray, class_id: int, width: int, height: int,
                   confidence: float, image_rgb: np.ndarray):
    """Clean the mask morphologically, then emit one item per significant contour.

    For classes that frequently glue top+skirt together, first try to split the
    region by dominant color before contour extraction.
    """
    # Open removes speckles, close fills pinholes (e.g. skin peeking through a blouse).
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(class_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=2)

    if class_id in SPLIT_CANDIDATE_CLASSES:
        split = _try_vertical_color_split(cleaned, image_rgb)
        if split is not None:
            upper_mask, lower_mask = split
            return (
                _contours_to_items(upper_mask, class_id, width, height, confidence, id_suffix="u")
                + _contours_to_items(lower_mask, class_id, width, height, confidence, id_suffix="l")
            )

    return _contours_to_items(cleaned, class_id, width, height, confidence)


class AnalyzeRequest(BaseModel):
    base64_image: str


@app.post("/analyze")
async def analyze_outfit(request: AnalyzeRequest):
    print(f"Received request with base64 image of length: {len(request.base64_image)}")

    try:
        base64_data = request.base64_image
        if base64_data.startswith('data:image'):
            base64_data = base64_data.split(',')[1]

        image_bytes = base64.b64decode(base64_data)
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = img.size
        image_rgb = np.array(img)
        print(f"Image opened: {width}x{height}")

        print("Running fashion segmentation...")
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            outputs = fashion_model(**inputs)

        logits = outputs.logits  # (1, num_classes, h, w) at the model's internal resolution

        # Full-resolution seg_map for polygon extraction.
        upsampled = torch.nn.functional.interpolate(
            logits, size=(height, width), mode='bilinear', align_corners=False
        )
        seg_map = upsampled.argmax(dim=1).squeeze().cpu().numpy()

        # Low-res probs for cheap mean-softmax confidence (tall pins produce huge full-res tensors).
        low_res_probs = torch.nn.functional.softmax(logits, dim=1).squeeze(0).cpu().numpy()
        low_res_seg = logits.argmax(dim=1).squeeze().cpu().numpy()
        print("Segmentation complete.")

        items = []
        for class_id in SHOPPABLE_CLASSES:
            confidence = _class_confidence(low_res_probs, low_res_seg, class_id)
            if confidence == 0.0:
                continue
            class_mask = _build_class_mask(seg_map, class_id)
            items.extend(_extract_items(class_mask, class_id, width, height, confidence, image_rgb))

        print(f"Successfully extracted {len(items)} clothing items.")
        return {
            "status": "success",
            "message": f"Processed image. Found {len(items)} items.",
            "image_size": {"width": width, "height": height},
            "items": items,
        }

    except Exception as e:
        print(f"CRITICAL ERROR processing image: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Backend Error: {str(e)}",
            "items": [],
        }

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Qlothi API Server</title>
            <style>
                body { font-family: -apple-system, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f8f9fa; color: #111; }
                .container { text-align: center; padding: 40px; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
                h1 { font-size: 2rem; margin-bottom: 0.5rem; letter-spacing: -0.5px; }
                p { color: #666; margin-bottom: 2rem; }
                footer { font-size: 14px; color: #888; font-weight: 500; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✨ Qlothi Backend API</h1>
                <p>The AI segmentation engine is online and listening for extension requests.</p>
                <footer>Made with ❤️ by <strong>Kobuilds</strong></footer>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
