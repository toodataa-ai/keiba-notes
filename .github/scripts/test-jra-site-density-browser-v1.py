#!/usr/bin/env python3
"""Render public JRA pages at mobile and desktop viewport sizes."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from functools import partial
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

SITE = Path("docs").resolve()
OUT = Path("site-typography-screenshots")
OUT.mkdir(exist_ok=True)
httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(SITE)))
thread = Thread(target=httpd.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{httpd.server_port}"
opts = webdriver.ChromeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--force-device-scale-factor=1")
opts.add_argument("--disable-features=Translate")
driver = webdriver.Chrome(options=opts)
try:
    scenarios = {
        "mobile": (390, 844, ["index", "this-week", "schedule", "results", "methodology", "e2e"]),
        "desktop": (1280, 900, ["index", "this-week", "schedule"]),
    }
    for device, (w, h, pages) in scenarios.items():
        driver.set_window_size(w, h)
        for name in pages:
            driver.get(base + "/" + name + ".html")
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
            assert driver.title and len(driver.find_elements(By.TAG_NAME, "h1")) == 1,(device,name,"h1")
            sizes = driver.execute_script("""
                let q=s=>document.querySelector(s);
                let size=e=>e?parseFloat(getComputedStyle(e).fontSize):null;
                return {
                    viewport:innerWidth, width:document.documentElement.scrollWidth,
                    base:size(document.body),
                    h1:size(q("h1")),
                    h2:size(q(".page-section h2")),
                    race:size(q(".week-race strong")),
                    logo:size(q(".brand-title.brand-lockup")),
                    grid:q(".week-race")?getComputedStyle(q(".week-race")).gridTemplateColumns:null,
                    time:q(".week-race time")?getComputedStyle(q(".week-race time")).gridColumn:null
                };
            """)
            assert 12.5 <= sizes["base"] <= 15, (device,name,sizes)
            if device == "mobile":
                assert sizes["h1"] < 28,(device,name,sizes)
                if name in ("index","this-week","schedule","results"):
                    assert sizes["width"] <= sizes["viewport"]+2,(device,name,"horizontal overflow",sizes)
                if name=="this-week":
                    assert sizes["h1"] <= 24 and sizes["h2"] <= 20,(device,name,sizes)
                    if sizes["grid"]:
                        assert sizes["race"] <= 14 and len(sizes["grid"].split())==3,(device,name,sizes)
                        assert sizes["time"]=="auto",(device,name,sizes)
                if name=="index":
                    assert sizes["logo"] <= 23,(device,name,sizes)
            driver.save_screenshot(str(OUT / f"{device}-{name}.png"))
            print("PASS",device,name,sizes,flush=True)
finally:
    driver.quit()
    httpd.shutdown()
