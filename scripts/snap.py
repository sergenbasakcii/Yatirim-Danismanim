"""
Yatırım Danışmanım — Visual Snapshot Tool
==========================================
Streamlit uygulamasından her sayfanın PNG ekran görüntüsünü alır,
`scripts/snapshots/` altına kaydeder. UI değişiklikleri sonrası
görsel regresyon karşılaştırması için kullanılır.

KURULUM (bir kez):
    pip install playwright
    playwright install chromium

KULLANIM:
    # Streamlit'i ayrı terminalde başlat: streamlit run web_app.py
    python scripts/snap.py                  # tüm sayfalar
    python scripts/snap.py --page dashboard # tek sayfa
    python scripts/snap.py --viewport 1920x1080
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("HATA: playwright yüklü değil.")
    print("Kur: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_URL = "http://localhost:8501"
OUT_DIR  = Path(__file__).parent / "snapshots"
OUT_DIR.mkdir(exist_ok=True)

# Sayfa key → Streamlit query param (web_app.py routing'i ile uyumlu)
PAGES = {
    "login":        "/",
    "dashboard":    "/?p=dashboard",
    "opportunities":"/?p=opportunities",
    "analysis":     "/?p=analysis",
    "portfolio":    "/?p=portfolio",
    "projection":   "/?p=projection",
    "decision":     "/?p=decision_assistant",
}


def snap(page_key: str, url_suffix: str, viewport: tuple[int, int], full_page: bool) -> Path:
    out = OUT_DIR / f"{page_key}_{viewport[0]}x{viewport[1]}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            device_scale_factor=2,  # retina-quality
        )
        page = ctx.new_page()
        page.goto(BASE_URL + url_suffix, wait_until="networkidle", timeout=30_000)
        # Streamlit'in tüm widget'ları render etmesi için ek bekleme
        time.sleep(2)
        page.screenshot(path=str(out), full_page=full_page)
        browser.close()
    print(f"  ✓ {out.relative_to(Path.cwd())}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", choices=list(PAGES), help="Tek sayfa yakala")
    ap.add_argument("--viewport", default="1440x900", help="WxH (örn: 1920x1080)")
    ap.add_argument("--full-page", action="store_true", help="Tüm scroll'u dahil et")
    args = ap.parse_args()

    try:
        w, h = (int(x) for x in args.viewport.lower().split("x"))
    except ValueError:
        print(f"HATA: --viewport formatı hatalı: {args.viewport}")
        return 2

    targets = [args.page] if args.page else list(PAGES)
    print(f"Snapshotting {len(targets)} page(s) @ {w}x{h}...")
    for key in targets:
        try:
            snap(key, PAGES[key], (w, h), args.full_page)
        except Exception as e:
            print(f"  ✗ {key}: {e}")
    print(f"\nÇıktı: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
