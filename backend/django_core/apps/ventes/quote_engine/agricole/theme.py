# flake8: noqa
"""TAQINOR quote engine — AGRICOLE renderer (brand tokens + shared CSS).

The premium multi-page agricultural (pompage solaire) proposal. Part of the
single quote engine (`apps/ventes/quote_engine`); selected for
`mode_installation == agricole` (full format) by `agricole.renderer`. Reuses the
engine's bundled fonts/logo (one level up at quote_engine/assets), exactly like
the residential package, so the brand stays identical across markets.
"""
from __future__ import annotations
import base64
from pathlib import Path

# Engine assets (fonts + logo), one level up at quote_engine/assets.
_LIVE_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_FONT_DIR = _LIVE_ASSETS / "fonts"

# ── Brand palette (shared with residential) + agricole accents ──────────────
C = {
    "navy":      "#1A2B4A",
    "navy_900":  "#12203b",
    "navy_700":  "#243a5e",
    "gold":      "#F5A623",
    "gold_soft": "#FDF3E3",
    "green":     "#16A34A",
    "green_bg":  "#E8F5EC",
    "green_700": "#0F7A38",
    # Agricole accents: water blue + earth, for the pumping/irrigation story.
    "water":     "#2C5F8A",
    "water_bg":  "#EAF1F7",
    "earth":     "#8A5A2B",
    "ink":       "#1f2937",
    "muted":     "#6b7280",
    "muted_2":   "#9BA3AE",
    "line":      "#E5E7EB",
    "line_soft": "#EFF1F4",
    "paper":     "#FFFFFF",
    "wash":      "#F7F9FC",
    "wash_navy": "#0f1d36",
    "blue":      "#2C5F8A",
    "red":       "#C0392B",
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
    if not p.exists():
        return ""
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
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


# This renderer's own bundled assets (a page-1 hero photo — drop a real farm
# install photo at quote_engine/agricole/assets/hero.jpg; empty -> flat navy).
_AGRI_ASSETS = Path(__file__).resolve().parent / "assets"


def hero_image_b64(kwc=None, mode="agricole") -> str:
    """Hero photo for the cover: nearest-power installation photo from the shared
    library (agricole falls back to residential/industriel of similar kWc), else
    this package's own bundled hero.jpg, else "" (flat navy)."""
    try:
        from .. import installations          # Django: quote_engine.installations
    except ImportError:                        # standalone dev harness
        import installations
    b = installations.pick_b64(kwc, mode)
    if b:
        return b
    p = _AGRI_ASSETS / "hero.jpg"
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
    return f"{n:,.0f}".replace(",", " ")


def fmt_dec(n, decimals=1) -> str:
    """Decimal-comma FR number, trailing zeros trimmed (3.0 -> '3', 4.7 -> '4,7')."""
    try:
        f = float(n)
    except (TypeError, ValueError):
        return str(n)
    if f == int(f):
        return str(int(f))
    return f"{f:.{decimals}f}".rstrip("0").rstrip(".").replace(".", ",")


# French name particles that stay lowercase inside a name.
_NAME_PARTICLES = {"de", "du", "des", "la", "le", "les", "van", "von",
                   "el", "al", "ben", "bin", "ould", "aït", "ait"}


def titlecase_name(name) -> str:
    """Display-case a person's name: 'meryem hida' -> 'Meryem Hida'."""
    s = str(name or "").strip()
    if not s:
        return ""

    def cap_token(tok, first):
        if not tok:
            return tok
        if tok[1:] != tok[1:].lower():
            return tok
        low = tok.lower()
        if not first and low in _NAME_PARTICLES:
            return low
        return low[:1].upper() + low[1:]

    out = []
    for i, word in enumerate(s.split(" ")):
        parts = word.split("-")
        out.append("-".join(
            cap_token(p, first=(i == 0 and j == 0))
            for j, p in enumerate(parts)))
    return " ".join(out)


def join_meta(*parts, sep=" · ") -> str:
    """Join non-empty, stripped meta fragments with `sep`."""
    clean = [str(p).strip().strip(",").strip() for p in parts if p and str(p).strip()]
    return sep.join(c for c in clean if c)


def base_css() -> str:
    """Page frame + design tokens shared by all agricole pages."""
    return f"""
{font_face_css()}
* {{ margin:0; padding:0; box-sizing:border-box; }}
@page {{ size: A4; margin: 0; }}
html, body {{ font-family:{FONT_SANS}; color:{C['ink']}; -weasy-hyphens:none; }}
.page {{
  position:relative; width:210mm; height:297mm; overflow:hidden;
  background:{C['paper']}; page-break-after:always;
  -webkit-print-color-adjust:exact; print-color-adjust:exact;
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

/* Shared footer */
.foot {{
  position:absolute; left:0; right:0; bottom:0; height:13mm;
  background:{C['navy']}; color:#cdd5e2; display:flex; align-items:center;
  justify-content:space-between; padding:0 14mm; font-size:7.6pt;
}}
.foot b {{ color:#fff; font-weight:700; letter-spacing:.04em; }}
.foot a {{ color:{C['gold']}; text-decoration:none; }}

.card {{ border:1px solid {C['line']}; border-radius:12px; background:{C['paper']}; }}
.pill {{ display:inline-block; padding:3px 10px; border-radius:999px;
  font-size:7.6pt; font-weight:700; letter-spacing:.04em; }}
"""


def page_footer(data: dict) -> str:
    """Footer band. `{page}` is substituted per page by the render harness;
    the total page count comes from `data['pages_total']`."""
    site = data.get("site_url", "taqinor.ma")
    total = data.get("pages_total", 5)
    ref = data.get("ref", "")
    return f"""
<div class="foot">
  <div><b>TAQINOR</b> &nbsp;·&nbsp; contact@taqinor.com &nbsp;·&nbsp; +212 6 61 85 04 10</div>
  <div>Page {{page}} / {total} &nbsp;·&nbsp; Réf. {ref} &nbsp;·&nbsp; <a>{site}</a></div>
</div>
"""
