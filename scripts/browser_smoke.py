"""Optional integration test when local browser connections are permitted.

Install playwright and Chromium separately before invoking. Requires local API
server already running on http://127.0.0.1:8000.
"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={"width":1440,"height":900})
    page.goto("http://127.0.0.1:8000/",wait_until="networkidle")
    page.locator("#scenario-select option").first.wait_for()
    assert page.locator("#scenario-select option").count()>=5
    page.locator("#run-top").click()
    page.wait_for_function("document.getElementById('scene-status').textContent.includes('VERIFIED')",timeout=20000)
    assert page.locator("#run-progress").inner_text()=="100%"
    assert "EVENTS" in page.locator("#event-count").inner_text()
    page.screenshot(path="artifacts/browser-smoke.png",full_page=True)
    browser.close()
    print("Browser API/UI smoke test passed; screenshot saved.")
