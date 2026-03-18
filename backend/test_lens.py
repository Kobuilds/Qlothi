import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        print("Navigating...")
        await page.goto("https://images.google.com/")
        await page.screenshot(path="debug_google_start.png")
        html = await page.content()
        with open("debug_google.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved debug_google_start.png and debug_google.html")
        
        # Click camera icon
        try:
            camera_btn = await page.wait_for_selector('div[role="button"][aria-label="Search by image"]', timeout=5000)
            if camera_btn:
                print("Found camera button, clicking...")
                await camera_btn.click()
                await page.screenshot(path="debug_google_after_click.png")
                
                print("Waiting for file input...")
                file_input = await page.wait_for_selector('input[type="file"]', state="attached", timeout=5000)
                if file_input:
                    print("Found file input, uploading...")
                    await file_input.set_input_files("test_google.jpg") # need a dummy image
                    print("Waiting for visual matches to load...")
                    try:
                        await page.wait_for_selector('div[data-is-visual-match="true"], h3', timeout=10000)
                    except:
                        pass
                    await page.screenshot(path="debug_google_results.png")
                    with open("debug_google_results.html", "w", encoding="utf-8") as f:
                        f.write(await page.content())
                    print("Saved debug_google_results.png and debug_google_results.html")
                else:
                    print("Found file input.")
            else:
                print("Camera button not found.")
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="debug_google_error.png")
            
        await browser.close()

asyncio.run(main())
