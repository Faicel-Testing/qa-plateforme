"""Take screenshots of KPI dashboard and Allure report."""
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))

opts = Options()
opts.add_argument("--headless")
opts.add_argument("--window-size=1600,900")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--force-device-scale-factor=1")

driver = webdriver.Chrome(options=opts)

try:
    # ── 1. KPI Dashboard ───────────────────────────────────────────────
    kpi_path = os.path.join(DOCS_DIR, "kpi-dashboard.html")
    driver.get(f"file:///{kpi_path.replace(os.sep, '/')}")
    time.sleep(3)  # let Chart.js render
    out = os.path.join(DOCS_DIR, "screenshot-kpi-dashboard.png")
    driver.save_screenshot(out)
    print("[OK] KPI dashboard -> " + out)

    # ── 2. Allure Report ───────────────────────────────────────────────
    driver.get("http://localhost:5050")
    time.sleep(5)  # let Angular app load
    out2 = os.path.join(DOCS_DIR, "screenshot-allure-report.png")
    driver.save_screenshot(out2)
    print("[OK] Allure report  -> " + out2)

finally:
    driver.quit()
