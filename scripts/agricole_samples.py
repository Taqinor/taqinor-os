#!/usr/bin/env python
"""Render the AGRICOLE sample proposals to HTML + PDF for preview.

Renders the SAME HTML the production engine renders, then prints it to PDF with
headless Chromium/Edge (WeasyPrint's native libs aren't available on this dev
box; production still uses WeasyPrint in Docker/CI). Output: docs/samples/agricole/.

    python scripts/agricole_samples.py
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = REPO / "backend" / "django_core" / "apps" / "ventes" / "quote_engine"
# 4-page version output. The 5-page version is frozen on the
# `agricole-quote-v5-5pages` tag (its samples live in docs/samples/agricole/).
OUT = REPO / "docs" / "samples" / "agricole_4p"

# Import the agricole package standalone (no Django needed for company=None).
sys.path.insert(0, str(ENGINE))

import agricole  # noqa: E402
from agricole import render, renderer, sample_data  # noqa: E402


def _find_browser() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    browser = _find_browser()
    results = []
    for key in sample_data.keys():
        data = renderer._augment(sample_data.build(key))
        html = render.build_html(data)
        html_path = OUT / f"agricole-{key}.html"
        html_path.write_text(html, encoding="utf-8")
        pdf_path = OUT / f"agricole-{key}.pdf"
        if browser:
            import tempfile
            profile = tempfile.mkdtemp(prefix=f"edge-{key}-")
            subprocess.run([
                browser, "--headless=new", "--disable-gpu", "--no-sandbox",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
                html_path.as_uri(),
            ], check=False, timeout=120,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        results.append((key, html_path, pdf_path if browser else None))

    print("Rendered agricole samples:")
    for key, h, p in results:
        print(f"  · {key}: {h.relative_to(REPO)}"
              + (f"  +  {p.relative_to(REPO)}" if p and p.exists() else "  (HTML only)"))
    if not browser:
        print("No Edge/Chrome found — HTML written; open it in a browser to print PDF.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
