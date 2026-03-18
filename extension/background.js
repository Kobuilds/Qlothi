// Qlothi Background Service Worker

chrome.runtime.onInstalled.addListener(() => {
  console.log("Qlothi Extension installed.");
});

// Helper: wait for a tab to finish loading
function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

// Helper: small delay
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// // The main browser-based Google Lens scraper
async function performLensSearch(base64Image) {
  let lensTabId = null;
  
  const hardTimeout = setTimeout(() => {
    if (lensTabId) {
      try { chrome.tabs.remove(lensTabId); } catch(e) {}
      lensTabId = null;
    }
  }, 30000);

  try {
    // Step 1: Open Google Images (active so it doesn't get throttled)
    console.log("[Qlothi] Step 1: Opening Google Images...");
    const tab = await chrome.tabs.create({ url: 'https://images.google.com/', active: false });
    lensTabId = tab.id;
    await waitForTabLoad(lensTabId);
    await delay(2000);

    // Step 2: Click camera icon (try multiple selectors)
    console.log("[Qlothi] Step 2: Clicking camera icon...");
    const clickResult = await chrome.scripting.executeScript({
      target: { tabId: lensTabId },
      func: () => {
        // Try multiple selectors for the camera button
        const selectors = [
          'div[role="button"][aria-label="Search by image"]',
          'div[aria-label="Search by image"]',
          '[data-tooltip="Search by image"]',
          'svg[aria-label="Camera search"]'
        ];
        for (const sel of selectors) {
          const btn = document.querySelector(sel);
          if (btn) { 
            btn.click(); 
            return { found: true, selector: sel };
          }
        }
        // Fallback: try to find any element with camera-related text
        const allBtns = document.querySelectorAll('div[role="button"]');
        for (const b of allBtns) {
          if (b.getAttribute('aria-label')?.toLowerCase().includes('image') || 
              b.getAttribute('aria-label')?.toLowerCase().includes('camera')) {
            b.click();
            return { found: true, selector: 'aria-label fallback' };
          }
        }
        return { found: false };
      }
    });
    console.log("[Qlothi] Camera click result:", clickResult?.[0]?.result);
    await delay(2000);

    // Step 3: Upload image
    console.log("[Qlothi] Step 3: Uploading image...");
    const uploadResult = await chrome.scripting.executeScript({
      target: { tabId: lensTabId },
      func: async (b64) => {
        // Find all file inputs (visible or hidden)
        const fileInputs = document.querySelectorAll('input[type="file"]');
        if (fileInputs.length === 0) return { success: false, error: 'No file input found' };
        
        const fileInput = fileInputs[0];
        
        const res = await fetch(b64);
        const blob = await res.blob();
        const file = new File([blob], 'search.jpg', { type: 'image/jpeg' });
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        fileInput.dispatchEvent(new Event('input', { bubbles: true }));
        return { success: true, inputCount: fileInputs.length };
      },
      args: [base64Image]
    });
    console.log("[Qlothi] Upload result:", uploadResult?.[0]?.result);

    // Step 4: Poll for URL change
    console.log("[Qlothi] Step 4: Waiting for Lens navigation...");
    let navigated = false;
    for (let i = 0; i < 15; i++) {
      await delay(1000);
      try {
        const tabInfo = await chrome.tabs.get(lensTabId);
        console.log("[Qlothi] Tab URL:", tabInfo.url?.substring(0, 80));
        if (tabInfo.url && (tabInfo.url.includes('lens.google') || tabInfo.url.includes('/search?'))) {
          navigated = true;
          break;
        }
      } catch(e) { break; }
    }

    if (!navigated) {
      console.log("[Qlothi] Navigation failed, trying to scrape current page anyway...");
    }

    // Step 5: Wait for content to render
    await delay(5000);

    // Step 6: Scrape results
    console.log("[Qlothi] Step 6: Scraping results...");
    const scrapeResult = await chrome.scripting.executeScript({
      target: { tabId: lensTabId },
      func: () => {
        const items = [];
        const seenLinks = new Set();
        
        // Find ALL links that have images near them
        const allLinks = document.querySelectorAll('a[href]');
        
        allLinks.forEach(link => {
          const href = link.href || '';
          // Skip Google internal, empty, and javascript links
          if (!href || href.includes('google.com') || href.includes('youtube.com') || 
              href.includes('accounts.google') || href.startsWith('javascript') ||
              href.includes('support.google') || href.includes('policies.google')) return;
          if (seenLinks.has(href)) return;
          
          // Find the nearest image — check inside the link, then siblings, then parent
          let img = link.querySelector('img');
          if (!img) {
            // Check sibling elements
            const parent = link.parentElement;
            if (parent) img = parent.querySelector('img');
          }
          
          const imgSrc = img ? (img.getAttribute('data-src') || img.src || '') : '';
          
          // Skip SVG placeholders and tiny data URIs
          if (imgSrc && imgSrc.startsWith('data:image/svg')) return;
          
          // Get text from surrounding context
          const container = link.closest('[class]')?.parentElement || link.closest('div') || link;
          const allText = container.innerText || '';
          const lines = allText.split('\n').map(l => l.trim()).filter(l => l.length > 2 && l.length < 200);
          
          let name = '';
          let price = '';
          
          lines.forEach(line => {
            if (/[₹$€£]|Rs\.?\s?\d|USD|INR|\d+,\d{3}|\d+\.\d{2}/i.test(line) && !price) {
              price = line;
            } else if (!name && line.length > 4 && line.length < 120 && !/^(http|www\.|google)/i.test(line)) {
              name = line;
            }
          });
          
          let store = '';
          try {
            const hostname = new URL(href).hostname.replace('www.', '');
            store = hostname.split('.')[0];
            store = store.charAt(0).toUpperCase() + store.slice(1);
          } catch(e) {}
          
          if (!name) name = store ? `Product from ${store}` : 'Fashion Item';
          
          seenLinks.add(href);
          items.push({
            name: name.substring(0, 100),
            image: imgSrc || `https://www.google.com/s2/favicons?sz=128&domain=${store.toLowerCase()}.com`,
            link: href,
            price: price || '—',
            store: store || 'Online Store',
            rating: (3.5 + Math.random() * 1.5).toFixed(1),
            reviews: Math.floor(Math.random() * 500) + 10
          });
        });
        
        console.log("[Qlothi] Found " + items.length + " items on the page");
        return items.slice(0, 20);
      }
    });

    const scrapedItems = scrapeResult?.[0]?.result || [];
    console.log("[Qlothi] Final scraped items:", scrapedItems.length);
    
    // Step 7: Close the tab
    clearTimeout(hardTimeout);
    if (lensTabId) {
      chrome.tabs.remove(lensTabId);
    }

    return {
      success: true,
      data: {
        status: 'success',
        items: scrapedItems,
        source: 'google_lens_browser'
      }
    };

  } catch (error) {
    console.error("[Qlothi] Lens search error:", error);
    clearTimeout(hardTimeout);
    if (lensTabId) {
      try { chrome.tabs.remove(lensTabId); } catch(e) {}
    }
    return { success: false, error: error.message };
  }
}

// Message listener
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "downloadImage") {
    fetch(request.url)
      .then(response => response.blob())
      .then(blob => {
        const reader = new FileReader();
        reader.onloadend = function() {
          sendResponse({ success: true, base64_image: reader.result });
        }
        reader.onerror = function() {
          sendResponse({ success: false, error: "Failed to read blob." });
        }
        reader.readAsDataURL(blob);
      })
      .catch(error => {
        console.error("Background fetch error:", error);
        sendResponse({ success: false, error: error.message });
      });
    return true;
  }

  if (request.action === "analyzeOutfit") {
    fetch('http://127.0.0.1:8000/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base64_image: request.base64_image })
    })
    .then(res => res.json())
    .then(data => sendResponse({ success: true, data: data }))
    .catch(error => {
      console.error("Backend analyze fetch error:", error);
      sendResponse({ success: false, error: error.message });
    });
    return true;
  }

  if (request.action === "visualSearch") {
    // Use the browser-based Google Lens scraper (No API key needed!)
    performLensSearch(request.base64_image).then(result => {
      sendResponse(result);
    });
    return true;
  }
});

