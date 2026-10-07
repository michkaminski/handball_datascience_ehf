"""Save the one-page match summary as PDF and PNG.

Needs the app running (run.bat) and Playwright with Chromium (``playwright install chromium``).

    python scripts/export_match_summary.py 672 700 --out exports --lang both --variant both
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DEFAULT_URL = f"http://127.0.0.1:{os.environ.get('EHF_PORT', '5151')}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("match_ids", nargs="+", type=int)
    parser.add_argument("--url", default=DEFAULT_URL, help=f"app address (default {DEFAULT_URL})")
    parser.add_argument("--out", default="exports", help="output folder (default: exports)")
    parser.add_argument("--lang", choices=("pl", "en", "both"), default="pl", help="language (default: pl)")
    parser.add_argument(
        "--variant", choices=("full", "short", "both"), default="full", help="full or short page (default: full)"
    )
    parser.add_argument("--scale", type=float, default=3.0, help="PNG pixel density (3 ≈ 230 dpi on A4)")
    args = parser.parse_args()

    languages = ("pl", "en") if args.lang == "both" else (args.lang,)
    variants = ("full", "short") if args.variant == "both" else (args.variant,)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(device_scale_factor=args.scale, viewport={"width": 900, "height": 1300})
        for match_id in args.match_ids:
            for variant in variants:
                for lang in languages:
                    print(export(page, args.url, match_id, lang, variant, out))
        browser.close()


def export(page: Page, base_url: str, match_id: int, lang: str, variant: str, out: Path) -> str:
    query = f"lang={lang}" + ("&variant=short" if variant == "short" else "")
    response = page.goto(f"{base_url}/mecze/{match_id}/podsumowanie?{query}", wait_until="networkidle")
    if response is None or not response.ok:
        return f"{match_id} {variant} {lang}: HTTP {response.status if response else '?'} – skipped"
    suffix = "_short" if variant == "short" else ""
    stem = out / f"match_{match_id}{suffix}_{lang}"
    page.emulate_media(media="print")
    page.pdf(path=f"{stem}.pdf", format="A4", print_background=True, prefer_css_page_size=True)
    page.emulate_media(media="screen")
    page.locator(".page").screenshot(path=f"{stem}.png")
    return f"{match_id} {variant} {lang}: {stem}.pdf, {stem}.png"


if __name__ == "__main__":
    main()
