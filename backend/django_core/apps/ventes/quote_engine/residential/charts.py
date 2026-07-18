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

_MONTHS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
           "Juil", "Aoû", "Sep", "Oct", "Nov", "Déc"]


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
    """QRES19 — barres APPARIÉES (gris|or côte à côte) : la superposition
    pouvait se lire comme un empilement. Le mois de pointe porte l'étiquette
    « −X % » (l'économie réelle de CE mois), l'axe Y est étiqueté MAD."""
    import numpy as np
    x = np.arange(12)
    fig, ax = plt.subplots(figsize=(w, h))
    bw = 0.34
    grey = "#BFC9D6"          # ~12 % plus sombre que l'ancien gris (netteté)
    for xi, (b, a) in enumerate(zip(bills_before, bills_after)):
        ax.bar(xi - 0.19, b, bw, color=grey, edgecolor="none", zorder=2)
        ax.bar(xi + 0.19, a, bw, color=GOLD, edgecolor="none", zorder=3)
    ymax = max(list(bills_before) + [1])
    ax.set_ylim(0, ymax * 1.22)
    # Étiquette « −X % » sur le mois de pointe (calculée, jamais inventée).
    peak = int(np.argmax(bills_before))
    pb, pa = bills_before[peak], bills_after[peak]
    if pb > 0 and pa < pb:
        cut = round((1 - pa / pb) * 100)
        ax.annotate(f"−{cut} %", (peak, pb), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=8.2, color=GOLD,
                    fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(_MONTHS, fontsize=7.5, color=MUTED)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", " ")))
    ax.text(0.0, 1.03, "MAD", transform=ax.transAxes, fontsize=7,
            color=MUTED, ha="left", va="bottom")
    _clean(ax)
    ax.margins(x=0.02)
    # No in-chart legend — the card header already labels the two series, so the
    # plot stays clean and gets the full height.
    fig.tight_layout()
    return _uri(fig)


def coverage_donut(pct, w=1.95, h=1.95) -> str:
    pct = max(0, min(100, int(round(pct))))
    fig, ax = plt.subplots(figsize=(w, h))
    # QRES21 — anneau +25 % plus épais, piste résiduelle légèrement teintée
    # navy : l'anneau se lit mieux à taille imprimée.
    ax.pie([pct, 100 - pct], colors=[GOLD, "#DEE4ED"], startangle=90,
           counterclock=False,
           wedgeprops=dict(width=0.32, edgecolor="white", linewidth=1.4))
    # Typographie française : espace fine avant le %.
    ax.text(0, 0.08, f"{pct} %", ha="center", va="center",
            fontsize=22, color=NAVY, fontweight="bold")
    ax.text(0, -0.32, "couverture", ha="center", va="center",
            fontsize=8.5, color=MUTED)
    ax.set(aspect="equal")
    return _uri(fig)


def payback_curve(total_sans, total_avec, eco_s, eco_a, roi_s, roi_a,
                  w=6.9, h=2.35, cashflow_sans=None, cashflow_avec=None,
                  deux=True, avec_ok=True) -> str:
    import numpy as np
    years = np.arange(0, 26)
    # QX39 — quand le cumul du cashflow 25 ans réel est fourni (dégradation
    # panneau + escalade tarifaire + rendement batterie + remplacement
    # onduleur), on le TRACE tel quel (la courbe cesse d'impliquer des économies
    # plates sur 25 ans). Repli : ancienne droite linéaire éco × année.
    if cashflow_sans and cashflow_avec and len(cashflow_sans) >= 25:
        cs = np.array([-total_sans / 1000]
                      + [v / 1000 for v in cashflow_sans[:25]])
        ca = np.array([-total_avec / 1000]
                      + [v / 1000 for v in cashflow_avec[:25]])
    else:
        cs = np.array([(-total_sans + eco_s * y) / 1000 for y in years])
        ca = np.array([(-total_avec + eco_a * y) / 1000 for y in years])

    # QRES3 — un devis MONO-option ne trace qu'UNE courbe (celle de l'option
    # réelle) : plus de scénario « Avec batterie » fantôme ni de double
    # étiquette « rentabilisé » qui se chevauchent sur un devis réseau seul.
    if deux:
        series = [(cs, NAVY, "Sans batterie", roi_s, 13),
                  (ca, GOLD, "Avec batterie", roi_a, -24)]
        fill_curve = ca
    else:
        one = (ca, GOLD, None, roi_a, 13) if avec_ok else (cs, NAVY, None, roi_s, 13)
        series = [one]
        fill_curve = one[0]

    fig, ax = plt.subplots(figsize=(w, h))

    # QRES20 — la courbe raconte le REMBOURSEMENT : zone d'investissement
    # (sous zéro) lavée de bleu, zone de gain (au-dessus) lavée d'or, ligne de
    # zéro = « seuil de rentabilité » nommé, et le point de bascule posé SUR
    # le franchissement du zéro (là où l'œil cherche le moment du payback).
    ax.fill_between(years, fill_curve, 0, where=(fill_curve > 0), color=GOLD,
                    alpha=0.10, zorder=1, interpolate=True)
    ax.fill_between(years, fill_curve, 0, where=(fill_curve < 0), color=NAVY,
                    alpha=0.05, zorder=1, interpolate=True)
    ax.axhline(0, color="#9AA6B5", linewidth=1.3, zorder=2)
    # QRES51 — polices de la courbe AGRANDIES partout (retour fondateur : le
    # graphe n'était pas assez lisible). Décalée du bord droit pour ne jamais
    # frôler le repère « 25 » de l'axe.
    # AU-DESSUS de la ligne de zéro (sous elle, l'étiquette tombait sur les
    # repères de l'axe quand le zéro est bas — payback très court).
    ax.annotate("seuil de rentabilité", (24.2, 0),
                textcoords="offset points", xytext=(0, 4), fontsize=8.2,
                color=MUTED, ha="right", va="bottom")

    for curve, col, label, _roi, _dy in series:
        ax.plot(years, curve, color=col, linewidth=2.9, label=label,
                zorder=4, solid_capstyle="round")

    # Break-even dots ON the zero crossing (that IS the payback moment).
    # QRES60 — deux ROI proches → points plus petits (ils fusionnaient
    # visuellement à pleine taille).
    rois = [roi for _c, _col, _l, roi, _d in series if roi]
    _dot_s = 80 if (len(rois) < 2 or abs(rois[0] - rois[1]) >= 0.8) else 52
    for curve, col, _label, roi, _dy in series:
        if not roi:
            continue
        ax.scatter([roi], [0], s=_dot_s, color=col, zorder=6,
                   edgecolor="white", linewidth=1.6, marker="o")
    # QRES15/20 — UNE étiquette intelligente : ROI proches → un libellé
    # combiné (plus jamais deux textes qui se chevauchent) ; mono-option →
    # le sien. Posée au-dessus du zéro, à droite du dernier point.
    if rois:
        def _fr(v):
            return f"{v:g}".replace(".", ",")
        uniq = sorted(set(rois))
        if len(uniq) == 1:
            lbl = f"rentabilisé en {_fr(uniq[0])} ans"
        else:
            lbl = f"rentabilisés en {_fr(uniq[0])} et {_fr(uniq[1])} ans"
        # Posée SOUS la ligne de zéro (le lavis d'investissement y est vide) —
        # au-dessus, elle recoupait les courbes qui montent.
        ax.annotate(lbl, (max(uniq), 0), textcoords="offset points",
                    xytext=(11, -14), fontsize=9, color=INK,
                    fontweight="bold")

    ax.set_xlim(0, 25)
    ymin = min(float(min(c[0] for c, *_ in series)) * 1.15, -1.0)
    ymax_v = max(float(max(c[-1] for c, *_ in series)), 1.0)
    ax.set_ylim(ymin, ymax_v * 1.08)
    ax.set_xlabel("Années", fontsize=9.5, color=MUTED)
    # QRES19 — plus d'axe vertical pivoté : étiquette horizontale compacte.
    ax.text(0.0, 1.03, "k MAD", transform=ax.transAxes, fontsize=8.5,
            color=MUTED, ha="left", va="bottom")
    ax.tick_params(labelsize=9, colors=MUTED)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", " ")))
    _clean(ax)
    if deux:
        ax.legend(loc="upper left", frameon=False, fontsize=10,
                  labelcolor=INK, handlelength=1.4)
    fig.tight_layout()
    return _uri(fig)


def roof_layout(nb_panneaux, w=2.9, h=2.2) -> str:
    """Clean top-down roof + panel array schematic.

    QRES22 — glyphe ILLUSTRATIF : au-delà de 16 panneaux, une grille figée de
    12 cellules élégantes (le nombre exact vit dans la stat voisine) — plus
    jamais le « blob QR » de 70 cellules illisibles.
    """
    import math
    if nb_panneaux > 16:
        nb_panneaux = 12
    cols = max(1, round(math.sqrt(nb_panneaux * 1.7)))
    rows = max(1, math.ceil(nb_panneaux / cols))
    fig, ax = plt.subplots(figsize=(w, h))
    ax.add_patch(FancyBboxPatch((0.03, 0.03), 0.94, 0.94,
                 boxstyle="round,pad=0,rounding_size=0.03",
                 linewidth=1.2, edgecolor="#CCD6E4", facecolor="#F4F7FB"))
    pad, gap = 0.10, 0.014
    gw = (0.94 - 2 * pad) / cols
    gh = (0.94 - 2 * pad) / rows
    placed = 0
    for r in range(rows):
        for c in range(cols):
            if placed >= nb_panneaux:
                break
            x = pad + 0.03 + c * gw
            y = pad + 0.03 + (rows - 1 - r) * gh
            ax.add_patch(FancyBboxPatch((x + gap, y + gap),
                         gw - 2 * gap, gh - 2 * gap,
                         boxstyle="round,pad=0,rounding_size=0.006",
                         linewidth=0.5, edgecolor=GOLD, facecolor=NAVY))
            placed += 1
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off"); ax.set(aspect="equal")
    return _uri(fig)


def build_all(data: dict) -> dict:
    _pb_kw = dict(
        cashflow_sans=data.get("cashflow_sans"),
        cashflow_avec=data.get("cashflow_avec"),
        deux=bool(data.get("deux_options", True)),
        avec_ok=bool(data.get("avec_ok", True)))
    _pb_args = (data["total_sans"], data["total_avec"],
                data["eco_s_ann"], data["eco_a_ann"],
                data["roi_s"], data["roi_a"])
    return {
        "bill": bill_before_after(data["bills_before"], data["bills_after"]),
        "coverage": coverage_donut(data["coverage_pct"]),
        "payback": payback_curve(*_pb_args, **_pb_kw),
        # QRES51 — variante PLEINE PAGE pour la page rentabilité dédiée :
        # ratio plus haut (la courbe affichée sur 182 mm gagne ~20 mm de
        # hauteur), mêmes données, mêmes polices (déjà agrandies — affichées
        # plus grand encore à cette échelle).
        "payback_xl": payback_curve(*_pb_args, h=3.2, **_pb_kw),
        "roof": roof_layout(data["nb_panneaux"]),
    }
