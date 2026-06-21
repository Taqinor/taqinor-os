# flake8: noqa
"""TAQINOR quote engine — v2 PROTOTYPE (parallel copy, NOT wired into /proposal).

Brand tokens + shared CSS + asset/font loaders. Reuses the live engine's
bundled fonts/logo (read-only) so v2 is a visual evolution, not a new brand.
Nothing here touches the working engine.
"""
from __future__ import annotations
import base64
from pathlib import Path

# Read-only reference to the LIVE engine's assets (never written).
_LIVE_ASSETS = Path(__file__).resolve().parent.parent / "quote_engine" / "assets"
_FONT_DIR = _LIVE_ASSETS / "fonts"

# ── Brand palette (extracted from the live engine) ──────────────────────────
C = {
    "navy":      "#1A2B4A",
    "navy_900":  "#12203b",
    "navy_700":  "#243a5e",
    "gold":      "#F5A623",
    "gold_soft": "#E8A020",
    "green":     "#16A34A",
    "green_bg":  "#e8f5e9",
    "ink":       "#1f2937",
    "muted":     "#6b7280",
    "muted_2":   "#9BA3AE",
    "line":      "#E5E7EB",
    "line_soft": "#EFF1F4",
    "paper":     "#FFFFFF",
    "wash":      "#F7F9FC",
    "wash_navy": "#0f1d36",
    "blue":      "#2C5F8A",
}

FONT_DISPLAY = "'DM Serif Display', Georgia, serif"
FONT_SERIF = "'Playfair Display', Georgia, serif"
FONT_SANS = "'DM Sans', system-ui, sans-serif"


def _font_b64(name: str) -> str:
    p = _FONT_DIR / name
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def logo_dark_b64() -> str:
    """Logo recolored white-on-transparent for navy headers."""
    from PIL import Image
    import io
    p = _LIVE_ASSETS / "logo.png"
    img = Image.open(p).convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r > 230 and g > 230 and b > 230:          # white bg -> transparent
                px[x, y] = (0, 0, 0, 0)
            elif r < 120 and g < 120 and b < 120:        # dark ink -> white
                px[x, y] = (255, 255, 255, a)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def logo_color_b64() -> str:
    p = _LIVE_ASSETS / "logo.png"
    return base64.b64encode(p.read_bytes()).decode()


# v2's own bundled assets (self-contained, like the live engine).
_V2_ASSETS = Path(__file__).resolve().parent / "assets"


def hero_image_b64(name: str = "hero.jpg") -> str:
    """Base64 JPEG of the page-1 hero photo (real installation). Swap the file
    at quote_engine_v2/assets/hero.jpg to change it. Empty string -> flat navy."""
    p = _V2_ASSETS / name
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def font_face_css() -> str:
    faces = [
        ("DM Serif Display", 400, "DMSerifDisplay-400.woff2"),
        ("Playfair Display", 400, "PlayfairDisplay-400.woff2"),
        ("Playfair Display", 700, "PlayfairDisplay-700.woff2"),
        ("DM Sans", 400, "DMSans-400.woff2"),
        ("DM Sans", 500, "DMSans-500.woff2"),
        ("DM Sans", 700, "DMSans-700.woff2"),
    ]
    out = []
    for fam, wt, fn in faces:
        b64 = _font_b64(fn)
        if not b64:
            continue
        out.append(
            f"@font-face{{font-family:'{fam}';font-weight:{wt};font-style:normal;"
            f"src:url('data:font/woff2;base64,{b64}') format('woff2');}}")
    return "\n".join(out)


def fmt(n) -> str:
    """1234567 -> '1 234 567' (thin-space groups, FR style)."""
    try:
        n = round(float(n))
    except (TypeError, ValueError):
        return str(n)
    return f"{n:,.0f}".replace(",", " ")


def base_css() -> str:
    """Page frame + design tokens shared by all three pages."""
    return f"""
{font_face_css()}
* {{ margin:0; padding:0; box-sizing:border-box; }}
@page {{ size: A4; margin: 0; }}
html, body {{ font-family:{FONT_SANS}; color:{C['ink']}; -weasy-hyphens:none; }}
.page {{
  position:relative; width:210mm; height:297mm; overflow:hidden;
  background:{C['paper']}; page-break-after:always;
}}
.page:last-child {{ page-break-after:auto; }}
.pad {{ padding:14mm 14mm 0 14mm; }}
.row {{ display:flex; }}
.gold {{ color:{C['gold']}; }}
.muted {{ color:{C['muted']}; }}
.serif {{ font-family:{FONT_SERIF}; }}
.display {{ font-family:{FONT_DISPLAY}; }}
.kicker {{ font-size:8.5pt; letter-spacing:.22em; text-transform:uppercase;
  color:{C['muted_2']}; font-weight:700; }}
.h-sec {{ font-family:{FONT_SERIF}; font-weight:700; font-size:15pt;
  color:{C['navy']}; }}

/* Shared footer (FIXED — no overlapping chips like the live page-1 bug) */
.foot {{
  position:absolute; left:0; right:0; bottom:0; height:13mm;
  background:{C['navy']}; color:#cdd5e2; display:flex; align-items:center;
  justify-content:space-between; padding:0 14mm; font-size:7.6pt;
}}
.foot b {{ color:#fff; font-weight:700; letter-spacing:.04em; }}
.foot a {{ color:{C['gold']}; text-decoration:none; }}

/* Reusable card */
.card {{ border:1px solid {C['line']}; border-radius:12px; background:{C['paper']}; }}
.pill {{ display:inline-block; padding:3px 10px; border-radius:999px;
  font-size:7.6pt; font-weight:700; letter-spacing:.04em; }}
"""


def page_footer(data: dict) -> str:
    site = data.get("site_url", "taqinor.ma")
    return f"""
<div class="foot">
  <div><b>TAQINOR</b> &nbsp;·&nbsp; contact@taqinor.com &nbsp;·&nbsp; +212 6 61 85 04 10</div>
  <div>Page {{page}} / 3 &nbsp;·&nbsp; Réf. {data['ref']} &nbsp;·&nbsp; <a>{site}</a></div>
</div>
"""
