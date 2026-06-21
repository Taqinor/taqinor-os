# flake8: noqa
"""Agricultural solar water-pumping system schematic — pure inline SVG.

No third-party deps, no disk I/O: ``build(params) -> str`` returns ONE inline
SVG 1.1 string (single ``<svg>`` root, explicit fill/stroke, font-family
"DejaVu Sans, Arial, sans-serif"), so it renders identically under WeasyPrint
and headless Chromium. viewBox 0 0 1000 340 → ~180mm wide in the A4 PDF.

Flow, left → right: Soleil → Panneaux PV → Variateur (VFD) → Pompe (forage
immergé / surface) → Bassin → Champ. Every ``params`` key is optional and
degrades gracefully — a label whose value is missing is omitted (never "None").
"""
from __future__ import annotations
import math

NAVY = "#1A2B4A"
GOLD = "#F5A623"
GREEN = "#16A34A"
BLUE = "#2C5F8A"
BLUE_FILL = "#DCEBF7"
WASH = "#F7F9FC"
LINE = "#E5E7EB"
INK = "#1f2937"
MUTED = "#6b7280"
WHITE = "#FFFFFF"
FONT = "DejaVu Sans, Arial, sans-serif"


def _blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip()
        return s == "" or s.lower() == "none"
    return False


def _f(v):
    if _blank(v) or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _thin(v):
    """FR thin-space integer; '' when not numeric."""
    n = _f(v)
    if n is None:
        return ""
    return f"{int(round(n)):,}".replace(",", " ")


def _dec(v, d=1):
    """FR decimal-comma; whole numbers drop the decimals; '' when not numeric."""
    n = _f(v)
    if n is None:
        return ""
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{n:.{d}f}".replace(".", ",")


def _esc(t):
    if t is None:
        return ""
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _cap(parts):
    return " · ".join(p for p in parts if p and str(p).strip())


def _text(x, y, content, size=12, fill=INK, weight="normal", anchor="middle"):
    if content is None or str(content).strip() == "":
        return ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}">{_esc(content)}</text>')


def _rrect(x, y, w, h, rx=12, fill=WHITE, stroke=LINE, sw=1.4):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{rx}" ry="{rx}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"/>')


def _line(x1, y1, x2, y2, stroke=LINE, sw=1.4, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"{d}/>')


def _circle(cx, cy, r, fill=WHITE, stroke="none", sw=1.4):
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


def _path(d, fill="none", stroke=INK, sw=1.4):
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def _poly(points, fill=INK):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}"/>'


def _arrow(x, y, direction="right", color=MUTED, s=7):
    if direction == "right":
        pts = [(x, y), (x - s, y - s * 0.6), (x - s, y + s * 0.6)]
    elif direction == "left":
        pts = [(x, y), (x + s, y - s * 0.6), (x + s, y + s * 0.6)]
    elif direction == "down":
        pts = [(x, y), (x - s * 0.6, y - s), (x + s * 0.6, y - s)]
    else:
        pts = [(x, y), (x - s * 0.6, y + s), (x + s * 0.6, y + s)]
    return _poly(pts, fill=color)


def _connector(x1, y, x2, color=MUTED, sw=2.0, label=None, lab_fill=MUTED):
    out = [_line(x1, y, x2 - 7, y, stroke=color, sw=sw),
           _arrow(x2, y, "right", color)]
    if label and str(label).strip():
        out.append(_text((x1 + x2) / 2, y - 8, label, size=10, fill=lab_fill,
                         weight="bold"))
    return "".join(out)


def _node(cx, top, w, h, title, body, accent=NAVY, c2=None, c3=None):
    x = cx - w / 2
    out = [_rrect(x, top, w, h, rx=12),
           f'<rect x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="4" '
           f'rx="2" ry="2" fill="{accent}"/>', body]
    ly = top + h + 17
    out.append(_text(cx, ly, title, size=12, fill=INK, weight="bold"))
    if c2 and str(c2).strip():
        ly += 14
        out.append(_text(cx, ly, c2, size=10, fill=MUTED))
    if c3 and str(c3).strip():
        ly += 13
        out.append(_text(cx, ly, c3, size=10, fill=MUTED))
    return "".join(out)


# ── Icons ────────────────────────────────────────────────────────────────────
def _icon_sun(cx, cy, r=15):
    out = []
    for i in range(8):
        a = math.radians(i * 45)
        out.append(_line(cx + math.cos(a) * (r + 4), cy + math.sin(a) * (r + 4),
                         cx + math.cos(a) * (r + 11), cy + math.sin(a) * (r + 11),
                         stroke=GOLD, sw=2.4))
    out.append(_circle(cx, cy, r, fill=GOLD, stroke="#E69412", sw=1.4))
    return "".join(out)


def _icon_panels(cx, cy):
    out = []
    x0, y0, pw, ph, sk = cx - 26, cy - 13, 52, 28, 8
    out.append(_poly([(x0 + sk, y0), (x0 + pw + sk, y0),
                      (x0 + pw, y0 + ph), (x0, y0 + ph)], fill=NAVY))
    for c in range(1, 3):
        out.append(_line(x0 + sk * (1 - c / 3) + pw * c / 3, y0,
                         x0 + pw * c / 3, y0 + ph, stroke="#3A5078", sw=1.0))
    out.append(_line(x0 + sk * 0.5, y0 + ph / 2, x0 + pw + sk * 0.5, y0 + ph / 2,
                     stroke="#3A5078", sw=1.0))
    out.append(_line(cx - 11, cy + ph / 2, cx - 11, cy + 20, stroke=MUTED, sw=2.0))
    out.append(_line(cx + 11, cy + ph / 2, cx + 11, cy + 20, stroke=MUTED, sw=2.0))
    return "".join(out)


def _icon_vfd(cx, cy):
    out = []
    bx, by, bw, bh = cx - 22, cy - 19, 44, 38
    out.append(_rrect(bx, by, bw, bh, rx=6, fill=WHITE, stroke=NAVY, sw=1.8))
    out.append(_circle(bx + 9, by + 8, 2.3, fill=GREEN))
    out.append(_circle(bx + 16, by + 8, 2.3, fill=GOLD))
    out.append(_path(f"M {bx + 7:.1f} {cy + 6:.1f} q 5 -14 11 0 t 11 0",
                     stroke=BLUE, sw=2.0))
    return "".join(out)


def _icon_reservoir(cx, cy):
    out = []
    bx, by, bw, bh = cx - 25, cy - 17, 50, 36
    out.append(_rrect(bx, by, bw, bh, rx=8, fill=WHITE, stroke=BLUE, sw=1.8))
    wl = by + bh * 0.42
    out.append(f'<rect x="{bx + 2:.1f}" y="{wl:.1f}" width="{bw - 4:.1f}" '
               f'height="{by + bh - wl - 3:.1f}" rx="4" fill="{BLUE_FILL}"/>')
    out.append(_path(f"M {bx + 3:.1f} {wl:.1f} q 6 -4 12 0 t 12 0 t 12 0 t 10 0",
                     stroke=BLUE, sw=1.4))
    return "".join(out)


def _icon_field(cx, cy):
    out = []
    ground = cy + 17
    out.append(_line(cx - 30, ground, cx + 30, ground, stroke="#A1A8B5", sw=1.6))
    out.append(_line(cx - 30, cy - 9, cx + 30, cy - 9, stroke=BLUE, sw=2.0))
    for dx in (-20, 0, 20):
        out.append(_path(f"M {cx + dx:.1f} {cy - 3:.1f} c -3 4 -3 7 0 7 "
                         f"c 3 0 3 -3 0 -7 z", fill=BLUE, stroke="none"))
    for dx in (-21, -1, 19):
        out.append(_line(cx + dx, ground, cx + dx, ground - 9, stroke="#7A5230", sw=2.0))
        out.append(_circle(cx + dx, ground - 13, 6.2, fill=GREEN, stroke="#0E7C36", sw=1.0))
    return "".join(out)


def _borehole(cx, params):
    """Pump-in-source column. Returns (svg, title, c2, c3)."""
    surface = (params.get("type_pompe") or "").strip().lower() == "surface"
    src = (params.get("source") or "").strip().lower()
    hmt = _thin(params.get("hmt_m"))
    prof = _thin(params.get("profondeur_m"))
    top, bottom, sw = 96, 300, 32
    sx = cx - sw / 2
    out = [_line(cx - 56, top, cx + 56, top, stroke="#A1A8B5", sw=1.8)]
    for i in range(-4, 5):
        out.append(_line(cx + i * 11, top, cx + i * 11 - 5, top + 6,
                         stroke="#C7CCD6", sw=1.0))
    if not surface:
        out.append(_rrect(sx, top, sw, bottom - top, rx=4, fill=WASH,
                          stroke="#B7BECC", sw=1.4))
        wt = top + (bottom - top) * 0.40
        out.append(f'<rect x="{sx + 1.5:.1f}" y="{wt:.1f}" width="{sw - 3:.1f}" '
                   f'height="{bottom - wt - 2:.1f}" fill="{BLUE_FILL}"/>')
        out.append(_path(f"M {sx + 2:.1f} {wt:.1f} q 4 -3 8 0 t 8 0 t 8 0",
                         stroke=BLUE, sw=1.4))
        py, ph, pw = bottom - 44, 30, sw - 12
        px = cx - pw / 2
        out.append(_rrect(px, py, pw, ph, rx=5, fill=NAVY, stroke="#0F1C33", sw=1.4))
        for k in range(1, 4):
            out.append(_line(px + 2, py + ph * k / 4, px + pw - 2, py + ph * k / 4,
                             stroke="#43597E", sw=1.0))
        out.append(_line(cx, py, cx, top, stroke=BLUE, sw=3.0))
        for k in range(3):
            yy = wt - 8 - k * 15
            out.append(_path(f"M {cx - 4:.1f} {yy:.1f} L {cx:.1f} {yy - 5:.1f} "
                             f"L {cx + 4:.1f} {yy:.1f}", stroke=WHITE, sw=1.6))
        if hmt:
            dx = sx - 16
            dt, db = top, py + ph / 2
            out.append(_line(dx, dt, dx, db, stroke=NAVY, sw=1.3))
            out.append(_arrow(dx, dt, "up", NAVY, 6))
            out.append(_arrow(dx, db, "down", NAVY, 6))
            ly = (dt + db) / 2
            out.append(f'<text x="{dx - 7:.1f}" y="{ly:.1f}" font-family="{FONT}" '
                       f'font-size="10" font-weight="bold" fill="{NAVY}" '
                       f'text-anchor="middle" transform="rotate(-90 {dx - 7:.1f} '
                       f'{ly:.1f})">HMT {_esc(hmt)} m</text>')
        if prof:
            dx = sx + sw + 12
            out.append(_line(dx, top, dx, bottom - 2, stroke=MUTED, sw=1.1, dash="3 3"))
            out.append(_arrow(dx, bottom - 2, "down", MUTED, 5))
            ly = (top + bottom) / 2
            out.append(f'<text x="{dx + 9:.1f}" y="{ly:.1f}" font-family="{FONT}" '
                       f'font-size="9" fill="{MUTED}" text-anchor="middle" '
                       f'transform="rotate(90 {dx + 9:.1f} {ly:.1f})">'
                       f'Prof. {_esc(prof)} m</text>')
        title = "Pompe immergée"
        cap_src = {"forage": "Forage", "puits": "Puits", "oued": "Oued",
                   "reseau": "Réseau"}.get(src, "Forage")
    else:
        wx, ww = cx + 4, 38
        out.append(_rrect(wx, top, ww, bottom - top, rx=6, fill=WASH,
                          stroke="#B7BECC", sw=1.4))
        wt = top + (bottom - top) * 0.30
        out.append(f'<rect x="{wx + 1.5:.1f}" y="{wt:.1f}" width="{ww - 3:.1f}" '
                   f'height="{bottom - wt - 2:.1f}" fill="{BLUE_FILL}"/>')
        out.append(_path(f"M {wx + 2:.1f} {wt:.1f} q 5 -3 10 0 t 10 0 t 10 0",
                         stroke=BLUE, sw=1.4))
        pw, ph = 42, 28
        px, py = cx - 52, top + 14
        out.append(_rrect(px, py, pw, ph, rx=6, fill=NAVY, stroke="#0F1C33", sw=1.4))
        out.append(_circle(px + pw * 0.34, py + ph / 2, 8, fill="#43597E",
                           stroke=WHITE, sw=1.2))
        out.append(_line(px - 4, py + ph, px + pw + 4, py + ph, stroke=MUTED, sw=2.4))
        out.append(_path(f"M {px + pw:.1f} {py + ph / 2:.1f} H {wx + ww / 2:.1f} "
                         f"V {wt + 12:.1f}", stroke=BLUE, sw=3.0))
        if hmt:
            dx = wx + ww + 12
            dt, db = top, wt + 12
            out.append(_line(dx, dt, dx, db, stroke=NAVY, sw=1.3))
            out.append(_arrow(dx, dt, "up", NAVY, 6))
            out.append(_arrow(dx, db, "down", NAVY, 6))
            ly = (dt + db) / 2
            out.append(f'<text x="{dx + 9:.1f}" y="{ly:.1f}" font-family="{FONT}" '
                       f'font-size="10" font-weight="bold" fill="{NAVY}" '
                       f'text-anchor="middle" transform="rotate(90 {dx + 9:.1f} '
                       f'{ly:.1f})">HMT {_esc(hmt)} m</text>')
        title = "Pompe de surface"
        cap_src = {"puits": "Puits", "oued": "Oued", "forage": "Forage",
                   "reseau": "Réseau"}.get(src, "Puits")
    cv = params.get("pump_cv")
    kw = _dec(params.get("pump_kw"), 1)  # 1 decimal, consistent with cover/study
    cv_txt = "" if _blank(cv) else f"{_esc(cv)} CV"
    power = " ".join(t for t in (cv_txt, f"({kw} kW)" if kw else "") if t)
    return "".join(out), title, (power or None), cap_src


def build(params: dict) -> str:
    p = dict(params or {})
    kwc = _dec(p.get("kwc"), 1)
    nb = _thin(p.get("nb_panneaux"))
    watt = _thin(p.get("watt"))
    debit = _dec(p.get("debit_m3h"), 1)
    m3j = _thin(p.get("m3_jour"))
    surface_ha = _dec(p.get("surface_ha"), 1)
    crop = "" if _blank(p.get("crop")) else _esc(p.get("crop"))

    panel_main = (f"{nb} × {watt} W" if nb and watt
                  else (f"{nb} panneaux" if nb else (f"{watt} W" if watt else "")))
    panel_cap = _cap([panel_main, f"{kwc} kWc" if kwc else ""])

    card_top, card_w, card_h = 30, 124, 80
    icon_cy = card_top + 40
    xs = [90, 262, 434, 600, 770, 922]
    out = [_rrect(8, 8, 984, 324, rx=16, fill=WASH, stroke=LINE, sw=1.2)]

    cy = icon_cy
    out.append(_connector(xs[0] + card_w / 2 - 18, cy, xs[1] - card_w / 2 + 4,
                          color=GOLD, sw=2.2, label="énergie", lab_fill="#B97A0F"))
    out.append(_connector(xs[1] + card_w / 2, cy, xs[2] - card_w / 2 + 4,
                          color=NAVY, sw=2.2, label="CC"))
    out.append(_connector(xs[2] + card_w / 2, cy, xs[3] - 60,
                          color=NAVY, sw=2.2, label="CA"))
    out.append(_connector(xs[3] + 60, cy, xs[4] - card_w / 2 + 4,
                          color=BLUE, sw=2.6, label=(f"{debit} m³/h" if debit else None),
                          lab_fill=BLUE))
    out.append(_connector(xs[4] + card_w / 2, cy, xs[5] - card_w / 2 + 4,
                          color=BLUE, sw=2.6, label=None, lab_fill=BLUE))

    out.append(_node(xs[0], card_top, card_w, card_h, "Soleil",
                     _icon_sun(xs[0], icon_cy), accent=GOLD))
    out.append(_node(xs[1], card_top, card_w, card_h, "Panneaux PV",
                     _icon_panels(xs[1], icon_cy), accent=NAVY, c2=panel_cap or None))
    out.append(_node(xs[2], card_top, card_w, card_h, "Variateur solaire",
                     _icon_vfd(xs[2], icon_cy), accent=NAVY, c2="VFD"))

    bore, b_title, b_c2, b_c3 = _borehole(xs[3], p)
    out.append(bore)
    by = 312
    out.append(_text(xs[3], by, b_title, size=12, fill=INK, weight="bold"))
    if b_c2:
        out.append(_text(xs[3], by + 14, b_c2, size=10, fill=MUTED))

    m3j_cap = f"≈ {m3j} m³/jour" if m3j else None
    out.append(_node(xs[4], card_top, card_w, card_h, "Bassin / Réservoir",
                     _icon_reservoir(xs[4], icon_cy), accent=BLUE, c2=m3j_cap))
    field_cap = _cap([f"{surface_ha} ha" if surface_ha else "", crop])
    out.append(_node(xs[5], card_top, card_w, card_h, "Champ / Culture",
                     _icon_field(xs[5], icon_cy), accent=GREEN, c2=field_cap or None))

    return (f'<svg viewBox="0 0 1000 340" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="{FONT}" role="img" '
            f'aria-label="Schéma système de pompage solaire agricole">'
            f'{"".join(out)}</svg>')
