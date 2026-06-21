# flake8: noqa
"""Premium AGRICOLE (pompage solaire) charts.

matplotlib -> transparent PNG data-URIs. Same calm, premium styling as the
residential charts: restrained palette, hairline grids, no chartjunk, generous
breathing room, brand-coloured accents. Every function is self-contained and
defensive — it never raises on empty / zero / missing input.
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

NAVY = "#1A2B4A"
GOLD = "#F5A623"
GREEN = "#16A34A"
BLUE = "#2C5F8A"     # water
GREY = "#D7DEE8"
GREY_2 = "#AEB8C7"
INK = "#1f2937"
MUTED = "#7A8699"
GRID = "#EEF1F6"
RED = "#C0392B"      # diesel

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


def _thin(v) -> str:
    """FR thin-space grouped integer (e.g. 12 345 -> '12 345')."""
    try:
        return f"{int(round(v)):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _fr_dec(v, decimals=2) -> str:
    """FR decimal-comma number (e.g. 0.44 -> '0,44')."""
    try:
        return f"{float(v):.{decimals}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "0," + "0" * decimals


def _series12(values):
    """Coerce input to exactly 12 finite floats (pad/truncate, NaN->0)."""
    import numpy as np
    out = []
    for x in (values or [])[:12]:
        try:
            f = float(x)
            out.append(f if np.isfinite(f) else 0.0)
        except (TypeError, ValueError):
            out.append(0.0)
    out += [0.0] * (12 - len(out))
    return out


def water_per_month(monthly_m3, w=6.6, h=1.95) -> str:
    """12 months of water delivered (m³) — BLUE bars."""
    import numpy as np
    vals = _series12(monthly_m3)
    x = np.arange(12)
    fig, ax = plt.subplots(figsize=(w, h))
    ax.bar(x, vals, 0.62, color=BLUE, edgecolor="none", zorder=3)
    ymax = max(vals + [1.0])
    ax.set_ylim(0, ymax * 1.16)
    ax.set_xticks(x); ax.set_xticklabels(_MONTHS, fontsize=7.5, color=MUTED)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _thin(v)))
    _clean(ax)
    ax.margins(x=0.02)
    fig.tight_layout()
    return _uri(fig)


def production_per_month(monthly_kwh, w=6.6, h=1.95) -> str:
    """12 months of PV production (kWh) — GOLD bars."""
    import numpy as np
    vals = _series12(monthly_kwh)
    x = np.arange(12)
    fig, ax = plt.subplots(figsize=(w, h))
    ax.bar(x, vals, 0.62, color=GOLD, edgecolor="none", zorder=3)
    ymax = max(vals + [1.0])
    ax.set_ylim(0, ymax * 1.16)
    ax.set_xticks(x); ax.set_xticklabels(_MONTHS, fontsize=7.5, color=MUTED)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _thin(v)))
    _clean(ax)
    ax.margins(x=0.02)
    fig.tight_layout()
    return _uri(fig)


def fuel_comparison(costs, w=6.6, h=2.15) -> str:
    """Annual running cost (MAD/an) — the killer comparison chart.

    Vertical grouped bars: Solaire / Butane aujourd'hui / Butane sans subvention
    / Diesel, value labelled on top of each bar.
    """
    import numpy as np
    costs = costs or {}

    def _v(k):
        try:
            f = float(costs.get(k, 0) or 0)
            return f if np.isfinite(f) and f >= 0 else 0.0
        except (TypeError, ValueError):
            return 0.0

    vals = [_v("solaire"), _v("butane_today"),
            _v("butane_future"), _v("diesel")]
    labels = ["Solaire", "Butane\naujourd'hui",
              "Butane\nsans subv.", "Diesel"]
    x = np.arange(4)

    fig, ax = plt.subplots(figsize=(w, h))

    # Solaire green, both butane in gold (future one faded + hatched to read as
    # "what it becomes without the subsidy"), diesel red.
    ax.bar(0, vals[0], 0.6, color=GREEN, edgecolor="none", zorder=3)
    ax.bar(1, vals[1], 0.6, color=GOLD, edgecolor="none", zorder=3)
    ax.bar(2, vals[2], 0.6, color=GOLD, edgecolor=GOLD, linewidth=0.8,
           alpha=0.45, hatch="////", zorder=3)
    ax.bar(3, vals[3], 0.6, color=RED, edgecolor="none", zorder=3)

    ymax = max(vals + [1.0])
    ax.set_ylim(0, ymax * 1.22)
    for xi, v in zip(x, vals):
        ax.annotate(_thin(v) + " MAD", (xi, v),
                    textcoords="offset points", xytext=(0, 4),
                    ha="center", va="bottom", fontsize=7.6,
                    color=NAVY, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.8, color=INK, linespacing=1.0)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _thin(v)))
    _clean(ax)
    ax.margins(x=0.06)
    fig.tight_layout()
    return _uri(fig)


def cost_per_m3(rates, w=3.0, h=2.0) -> str:
    """Cost per m³ of water pumped — small horizontal bars (GREEN/GOLD/RED)."""
    import numpy as np
    rates = rates or {}

    def _v(k):
        try:
            f = float(rates.get(k, 0) or 0)
            return f if np.isfinite(f) and f >= 0 else 0.0
        except (TypeError, ValueError):
            return 0.0

    # Top-to-bottom: Solaire, Butane, Diesel -> y positions reversed so Solaire
    # sits on top.
    names = ["Solaire", "Butane", "Diesel"]
    keys = ["solaire", "butane", "diesel"]
    cols = [GREEN, GOLD, RED]
    vals = [_v(k) for k in keys]
    y = np.arange(3)[::-1]

    fig, ax = plt.subplots(figsize=(w, h))
    ax.barh(y, vals, 0.58, color=cols, edgecolor="none", zorder=3)

    xmax = max(vals + [0.1])
    ax.set_xlim(0, xmax * 1.34)
    for yi, v in zip(y, vals):
        ax.annotate(_fr_dec(v) + " MAD/m³", (v, yi),
                    textcoords="offset points", xytext=(5, 0),
                    ha="left", va="center", fontsize=7.4,
                    color=NAVY, fontweight="bold")

    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=8, color=INK)
    ax.set_xticks([])
    for s in ("top", "right", "bottom", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    ax.margins(y=0.10)
    fig.tight_layout()
    return _uri(fig)


def payback_curve(total, annual_saving, years=20, w=6.6, h=2.2) -> str:
    """Cumulative net cashflow (k MAD) over `years` — single GOLD curve."""
    import numpy as np
    try:
        total = float(total)
        if not np.isfinite(total):
            total = 0.0
    except (TypeError, ValueError):
        total = 0.0
    try:
        annual_saving = float(annual_saving)
        if not np.isfinite(annual_saving):
            annual_saving = 0.0
    except (TypeError, ValueError):
        annual_saving = 0.0
    try:
        years = max(1, int(years))
    except (TypeError, ValueError):
        years = 20

    yr = np.arange(0, years + 1)
    cumul = np.array([(-total + annual_saving * y) / 1000.0 for y in yr])

    fig, ax = plt.subplots(figsize=(w, h))

    # Profit zone above break-even reads as money earned.
    ax.fill_between(yr, cumul, 0, where=(cumul > 0), color=GOLD, alpha=0.10,
                    zorder=1, interpolate=True)
    ax.axhline(0, color="#C5CCD6", linewidth=1, zorder=2)
    ax.plot(yr, cumul, color=GOLD, linewidth=2.6, zorder=4,
            solid_capstyle="round")

    # Break-even marker (only when there's a real saving).
    if annual_saving > 0 and total > 0:
        roi = total / annual_saving
        if 0 < roi <= years:
            ax.scatter([roi], [0], s=64, color=GOLD, zorder=6,
                       edgecolor="white", linewidth=1.6, marker="o")
            ax.annotate("rentabilisé\n" + _fr_dec(roi, 1) + " ans", (roi, 0),
                        textcoords="offset points", xytext=(7, 12),
                        fontsize=7.6, color=NAVY, fontweight="bold",
                        linespacing=1.0)

    ax.set_xlim(0, years); ax.margins(y=0.12)
    ax.set_xlabel("Années", fontsize=8, color=MUTED)
    ax.set_ylabel("Gain cumulé (k MAD)", fontsize=8, color=MUTED)
    ax.tick_params(labelsize=7.5, colors=MUTED)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _thin(v)))
    _clean(ax)
    fig.tight_layout()
    return _uri(fig)


def build_all(data: dict) -> dict:
    data = data or {}
    return {
        "water": water_per_month(data.get("water_monthly")),
        "production": production_per_month(data.get("prod_monthly")),
        "fuel": fuel_comparison(data.get("fuel_costs")),
        "cost_m3": cost_per_m3(data.get("cost_per_m3")),
        "payback": payback_curve(
            data.get("quote_total"), data.get("annual_saving")),
    }
