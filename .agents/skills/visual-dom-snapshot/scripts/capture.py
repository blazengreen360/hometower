#!/usr/bin/env python3
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed. Please run: pip install playwright && playwright install chromium")
    sys.exit(1)

def capture(url_path, out_file):
    target = f"http://localhost:8080{url_path}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        print(f"Navigating to {target}...")
        try:
            page.goto(target, wait_until="networkidle", timeout=10000)
            
            # Wait a small buffer to let animations/cytoscape js physically paint
            time.sleep(1.5)
            
            print(f"Snapshotting DOM to {out_file}...")
            page.screenshot(path=out_file, full_page=True)
            print(f"✅ Success! Visual DOM Proof saved to {out_file}")
            
        except Exception as e:
            print(f"🔴 FATAL: Playwright failed to capture DOM. Is the container running? Error: {e}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: capture.py <url_path> <out_file>")
        sys.exit(1)
    capture(sys.argv[1], sys.argv[2])
