# flake8: noqa
"""v2 PROTOTYPE charts (matplotlib -> transparent PNG data-URIs).

v3 elevation: calmer, more premium styling — restrained palette, hairline
grids, no chartjunk, generous breathing room, brand-coloured accents.
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
from matplotlib.patches import FancyBboxPatch

NAVY = "#1A2B4A"
GOLD = "#F5A623"
GREEN = "#16A34A"
GREY = "#D7DEE8"
GREY_2 = "#AEB8C7"
INK = "#1f2937"
MUTED = "#7A8699"
GRID = "#EEF1F6"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "text.color": INK,
    "axes.edgecolor": "#D8DEE8",
    "axes.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.titlecolor": NAVY,
})

_MONTHS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
           "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]


def _uri(fig, dpi=210) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, transparent=True,
                bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _clean(ax, keep_bottom=True):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(keep_bottom)
    ax.spines["bottom"].set_color("#D8DEE8")
    ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)


def bill_before_after(bills_before, bills_after, w=6.6, h=2.0) -> str:
    import numpy as np
    x = np.arange(12)
    fig, ax = plt.subplots(figsize=(w, h))
    bw = 0.40
    ax.bar(x - bw / 2 - 0.02, bills_before, bw, label="Facture ONEE aujourd'hui",
           color=GREY, edgecolor="none", zorder=3)
    ax.bar(x + bw / 2 + 0.02, bills_after, bw, label="Facture après solaire",
           color=GOLD, edgecolor="none", zorder=3)
    ax.set_xticks(x); ax.set_xticklabels(_MONTHS, fontsize=7.5, color=MUTED)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED)
    _clean(ax)
    ax.margins(x=0.01)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.20), ncol=2,
              frameon=False, fontsize=8, handlelength=1.0, handleheight=1.0,
              labelcolor=INK, columnspacing=1.6)
    fig.tight_layout()
    return _uri(fig)


def coverage_donut(pct, w=1.95, h=1.95) -> str:
    pct = max(0, min(100, int(round(pct))))
    fig, ax = plt.subplots(figsize=(w, h))
    ax.pie([pct, 100 - pct], colors=[GOLD, "#ECEFF4"], startangle=90,
           counterclock=False,
           wedgeprops=dict(width=0.26, edgecolor="white", linewidth=1.4))
    ax.text(0, 0.08, f"{pct}%", ha="center", va="center",
            fontsize=22, color=NAVY, fontweight="bold")
    ax.text(0, -0.32, "couverture", ha="center", va="center",
            fontsize=8.5, color=MUTED)
    ax.set(aspect="equal")
    return _uri(fig)


def payback_curve(total_sans, total_avec, eco_s, eco_a, roi_s, roi_a,
                  w=6.6, h=2.25) -> str:
    years = list(range(0, 26))
    cs = [(-total_sans + eco_s * y) / 1000 for y in years]
    ca = [(-total_avec + eco_a * y) / 1000 for y in years]
    fig, ax = plt.subplots(figsize=(w, h))
    ax.axhline(0, color="#C5CCD6", linewidth=1, zorder=1)
    ax.fill_between(years, ca, 0, where=[v > 0 for v in ca],
                    color=GOLD, alpha=0.08, zorder=1)
    ax.plot(years, cs, color=NAVY, linewidth=2.4, label="Sans batterie", zorder=3)
    ax.plot(years, ca, color=GOLD, linewidth=2.4, label="Avec batterie", zorder=3)
    for roi, col, dy in ((roi_s, NAVY, 12), (roi_a, GOLD, -20)):
        ax.scatter([roi], [0], s=40, color=col, zorder=5,
                   edgecolor="white", linewidth=1.2)
        ax.annotate(f"{roi:g} ans", (roi, 0), textcoords="offset points",
                    xytext=(4, dy), fontsize=8, color=col, fontweight="bold")
    ax.set_xlim(0, 25); ax.margins(y=0.08)
    ax.set_xlabel("Années", fontsize=8, color=MUTED)
    ax.set_ylabel("Gain cumulé (k MAD)", fontsize=8, color=MUTED)
    ax.tick_params(labelsize=7.5, colors=MUTED)
    _clean(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK,
              handlelength=1.4)
    fig.tight_layout()
    return _uri(fig)


def roof_layout(nb_panneaux, w=2.9, h=2.2) -> str:
    """Clean top-down roof + panel array schematic.

    Picks a tidy array (minimise empty cells, gently landscape) and centres any
    partial row, so we never leave a lone orphan square in a corner — e.g. 16
    panels render as a full 4×4, not 5×4 with one stray square.
    """
    import math
    n = max(1, int(round(nb_panneaux)))
    best = None
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        empty = rows * cols - n
        score = empty * 1.3 + abs(cols / rows - 1.5) + max(0, rows - cols) * 0.5
        if best is None or score < best[0]:
            best = (score, cols, rows)
    cols, rows = best[1], best[2]
    fig, ax = plt.subplots(figsize=(w, h))
    ax.add_patch(FancyBboxPatch((0.03, 0.03), 0.94, 0.94,
                 boxstyle="round,pad=0,rounding_size=0.03",
                 linewidth=1.2, edgecolor="#CCD6E4", facecolor="#F4F7FB"))
    pad, gap = 0.10, 0.014
    gw = (0.94 - 2 * pad) / cols
    gh = (0.94 - 2 * pad) / rows
    for r in range(rows):
        in_row = min(cols, n - r * cols)
        x_off = (cols - in_row) / 2.0          # centre a partial row
        for c in range(in_row):
            x = pad + 0.03 + (c + x_off) * gw
            y = pad + 0.03 + (rows - 1 - r) * gh
            ax.add_patch(FancyBboxPatch((x + gap, y + gap),
                         gw - 2 * gap, gh - 2 * gap,
                         boxstyle="round,pad=0,rounding_size=0.006",
                         linewidth=0.5, edgecolor=GOLD, facecolor=NAVY))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
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
