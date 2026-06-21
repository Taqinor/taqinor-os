"""v2 PROTOTYPE charts (matplotlib -> transparent PNG data-URIs).

New visuals vs the live engine:
  - bill_before_after : facture ONEE vs facture après solaire (the money hook)
  - coverage_donut    : taux de couverture / offset %
  - payback_curve     : 25-yr cumulative gain (kept, given real space)
  - roof_layout       : simple roof + panel-array schematic ("votre installation")
"""
from __future__ import annotations
import base64
import io
import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

NAVY = "#1A2B4A"
GOLD = "#F5A623"
GREEN = "#16A34A"
GREY = "#C9D2DE"
INK = "#1f2937"
MUTED = "#6b7280"

_MONTHS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
           "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]


def _uri(fig, dpi=200) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, transparent=True,
                bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def bill_before_after(bills_before, bills_after, w=6.6, h=2.05) -> str:
    """Grouped monthly bars: ONEE bill today vs bill after solar."""
    import numpy as np
    x = np.arange(12)
    fig, ax = plt.subplots(figsize=(w, h))
    bw = 0.42
    ax.bar(x - bw / 2, bills_before, bw, label="Facture ONEE aujourd'hui",
           color=GREY, edgecolor="none")
    ax.bar(x + bw / 2, bills_after, bw, label="Facture après solaire",
           color=GOLD, edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(_MONTHS, fontsize=7, color=MUTED)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED, length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#d8dee8")
    ax.grid(axis="y", color="#eef1f5", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2,
              frameon=False, fontsize=7.5, handlelength=1.1,
              labelcolor=INK, columnspacing=1.4)
    fig.tight_layout()
    return _uri(fig)


def coverage_donut(pct, w=1.9, h=1.9) -> str:
    """Single-value donut for taux de couverture (offset %)."""
    pct = max(0, min(100, int(round(pct))))
    fig, ax = plt.subplots(figsize=(w, h))
    ax.pie([pct, 100 - pct], colors=[GOLD, "#EAEEF4"], startangle=90,
           counterclock=False, wedgeprops=dict(width=0.30, edgecolor="white"))
    ax.text(0, 0.06, f"{pct}%", ha="center", va="center",
            fontsize=21, color=NAVY, fontweight="bold")
    ax.text(0, -0.34, "couverture", ha="center", va="center",
            fontsize=8, color=MUTED)
    ax.set(aspect="equal")
    return _uri(fig)


def payback_curve(total_sans, total_avec, eco_s, eco_a, roi_s, roi_a,
                  w=6.6, h=1.95) -> str:
    years = list(range(0, 26))
    cs = [-total_sans + eco_s * y for y in years]
    ca = [-total_avec + eco_a * y for y in years]
    fig, ax = plt.subplots(figsize=(w, h))
    ax.axhline(0, color="#c5ccd6", linewidth=1)
    ax.plot(years, cs, color=NAVY, linewidth=2.2, label="Sans batterie")
    ax.plot(years, ca, color=GOLD, linewidth=2.2, label="Avec batterie")
    ax.fill_between(years, cs, 0, where=[v > 0 for v in cs], color=NAVY, alpha=0.05)
    for roi, col in ((roi_s, NAVY), (roi_a, GOLD)):
        ax.scatter([roi], [0], s=34, color=col, zorder=5)
    ax.annotate(f"ROI {roi_s:g} ans", (roi_s, 0), textcoords="offset points",
                xytext=(2, 10), fontsize=7.5, color=NAVY, fontweight="bold")
    ax.annotate(f"ROI {roi_a:g} ans", (roi_a, 0), textcoords="offset points",
                xytext=(2, -16), fontsize=7.5, color=GOLD, fontweight="bold")
    ax.set_xlim(0, 25)
    ax.set_xlabel("Années", fontsize=7.5, color=MUTED)
    ax.tick_params(labelsize=7, colors=MUTED, length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#d8dee8")
    ax.grid(axis="y", color="#eef1f5", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, fontsize=7.5, labelcolor=INK)
    fig.tight_layout()
    return _uri(fig)


def roof_layout(nb_panneaux, w=2.7, h=2.0) -> str:
    """Schematic roof with a panel array (count-accurate-ish grid)."""
    import math
    cols = max(1, round(math.sqrt(nb_panneaux * 1.6)))
    rows = max(1, math.ceil(nb_panneaux / cols))
    fig, ax = plt.subplots(figsize=(w, h))
    # roof slab
    ax.add_patch(FancyBboxPatch((0.04, 0.04), 0.92, 0.92,
                 boxstyle="round,pad=0.0,rounding_size=0.02",
                 linewidth=1.4, edgecolor="#cfd8e6", facecolor="#f3f6fb"))
    pad, gap = 0.12, 0.012
    gw = (0.92 - 2 * (pad - 0.04)) / cols
    gh = (0.92 - 2 * (pad - 0.04)) / rows
    placed = 0
    for r in range(rows):
        for c in range(cols):
            if placed >= nb_panneaux:
                break
            x = (pad - 0.04) + c * gw + 0.04
            y = (pad - 0.04) + (rows - 1 - r) * gh + 0.04
            ax.add_patch(Rectangle((x + gap, y + gap), gw - 2 * gap, gh - 2 * gap,
                         facecolor=NAVY, edgecolor=GOLD, linewidth=0.5))
            placed += 1
    ax.text(0.5, -0.03, f"{nb_panneaux} panneaux", ha="center", va="top",
            transform=ax.transAxes, fontsize=8, color=MUTED)
    ax.set_xlim(0, 1); ax.set_ylim(-0.08, 1)
    ax.axis("off"); ax.set(aspect="equal")
    return _uri(fig)


def build_all(data: dict) -> dict:
    return {
        "bill": bill_before_after(data["bills_before"], data["bills_after"]),
        "coverage": coverage_donut(data["coverage_pct"]),
        "payback": payback_curve(
            data["total_sans"], data["total_avec"],
            data["eco_s_ann"], data["eco_a_ann"], data["roi_s"], data["roi_a"]),
        "roof": roof_layout(data["nb_panneaux"]),
    }
