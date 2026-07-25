"""Capture screenshots of the running app via headless Chromium.

    backend/.venv/bin/python make_screenshots.py

Requires the backend (:8000) and frontend (:5173) to be running.
Writes PNGs into docs/screenshots/.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:5173"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000},
                                device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector(".inbox-list li", timeout=15000)
        time.sleep(0.5)

        # 1 - review queue
        page.screenshot(path=str(OUT / "01_review_queue.png"))
        print("captured review queue")

        # open a flagged, still-to-review invoice
        page.get_by_role("button", name="To review").click()
        page.wait_for_selector(".inbox-list li:has(.inbox-issues)", timeout=10000)
        page.locator(".inbox-list li:has(.inbox-issues)").first.click()
        page.wait_for_selector(".split", timeout=10000)
        page.wait_for_selector(".overlay rect", timeout=10000)
        time.sleep(1.0)  # let the page image and boxes settle

        # 2 - verification screen
        page.screenshot(path=str(OUT / "02_verification.png"))
        print("captured verification screen")

        # 3 - line-item coding: assign a project to each row
        selects = page.locator(".lineitems select")
        n = selects.count()
        codes = ["4412", "4501", "4720", "9000"]
        for i in range(n):
            selects.nth(i).select_option(codes[i % len(codes)])
        time.sleep(0.4)
        page.locator(".rightpanel").screenshot(path=str(OUT / "03_coding.png"))
        print("captured line-item coding")

        # 4 - approve, wait for Marathon delivery, expand history
        page.locator("button.approve").click()
        page.wait_for_selector(".handover-delivered", timeout=20000)
        page.locator(".history-head").click()
        page.wait_for_selector(".history-list", timeout=5000)
        time.sleep(0.4)
        page.locator(".rightpanel").screenshot(path=str(OUT / "04_history_handover.png"))
        print("captured history + handover")

        browser.close()
    print("screenshots in", OUT)


if __name__ == "__main__":
    run()
