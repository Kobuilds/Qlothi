// Background service worker
chrome.runtime.onInstalled.addListener(() => {
  console.log("Qlothi Extension installed.");
});

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
      
    // Return true to indicate we will send a response asynchronously
    return true;
  }
});
