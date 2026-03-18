# Qlothi: AI-Powered Fashion Hub for Pinterest

**Qlothi** is a Chrome extension that transforms your Pinterest experience into a smart fashion shopping and analysis tool. With Qlothi, you can analyze outfits within images, segment individual clothing items, and find similar products across the web using Google Lens integration.

---

## 🚀 Key Features

- **Outfit Segmentation**: Uses the `Segformer` (MATTMDJAGA/segformer_b2_clothes) transformer model to accurately identify and segment hats, sunglasses, upper clothes, skirts, pants, dresses, belts, bags, and scarves.
- **Visual Search**: Integrated Google Lens visual search to find exact or similar matches for segmented items.
- **Interactive UI**: A sleek, glassmorphism-inspired overlay that fits naturally into the Pinterest interface.
- **Smart Filtering**: Filter search results by budget, style, or luxury categories.

---

## 🛠️ Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **AI Models**: Hugging Face Transformers (`Segformer`), PyTorch, OpenCV
- **Web Automation**: [Playwright](https://playwright.dev/python/) & BeautifulSoup4 for Google Lens integration

### Frontend (Chrome Extension)
- **Standard**: Manifest V3
- **Logic**: Vanilla JavaScript
- **Styling**: Vanilla CSS (Premium Glassmorphism Design)

---

## 📦 Project Structure

```bash
Qlothi/
├── backend/            # FastAPI server & AI logic
│   ├── main.py        # API endpoints and model integration
│   └── requirements.txt
├── extension/          # Chrome extension files
│   ├── manifest.json
│   ├── content.js      # Pinterest DOM interaction
│   └── background.js   # Service worker
└── README.md
```

---

## ⚙️ Setup Instructions

### 1. Backend Setup (Windows/Linux/macOS)

1. Navigate to the backend directory:
   ```powershell
   cd backend
   ```
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # source venv/bin/activate # Linux/macOS
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Install Playwright browsers:
   ```powershell
   playwright install chromium
   ```
5. Start the server:
   ```powershell
   python main.py
   ```
   *The server will run at `http://localhost:8000`.*

### 2. Chrome Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (top right corner).
3. Click **Load unpacked**.
4. Select the `extension` folder within the Qlothi project directory.

---

## 💡 Usage

1. Open any [Pinterest](https://www.pinterest.com) pin containing an outfit.
2. Click the **Analyze Outfit** button (integrated into the Pinterest UI).
3. Interact with the segmented clothing items to find similar products.

---

## ⚖️ License
MIT License. Created with ❤️ for fashion enthusiasts.
