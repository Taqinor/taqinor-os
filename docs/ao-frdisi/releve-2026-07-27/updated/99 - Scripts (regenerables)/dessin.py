# -*- coding: utf-8 -*-
"""Moteur de dessin technique pour les plans de relevé (matplotlib).

Conventions :
  - unités modèle = mètres ; feuille A3 paysage ; échelle indiquée au cartouche
  - cotes : lignes d'attache + ligne de cote à flèches + texte orienté
  - couleurs : géométrie noir, cotes bleu (#1d4ed8), incertain orange (#d97706),
    reconstruit/non mesuré gris (#64748b)
"""
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, FancyArrowPatch

BLEU = "#1d4ed8"
ORANGE = "#d97706"
GRIS = "#64748b"
NOIR = "#111111"

def new_sheet(title, subtitle, xlim, ylim, figsize=(16.54, 11.69)):
    """A3 paysage (pouces). Retourne fig, ax."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    # cadre
    fig.text(0.015, 0.975, title, fontsize=13, fontweight="bold", va="top")
    fig.text(0.015, 0.952, subtitle, fontsize=8.5, va="top", color="#333333")
    return fig, ax

def cartouche(fig, lines, x=0.665, y=0.02, w=0.32, h=0.115):
    """Cartouche en bas à droite (coordonnées figure)."""
    rect = plt.Rectangle((x, y), w, h, transform=fig.transFigure,
                         facecolor="white", edgecolor="black", lw=1.2, zorder=50)
    fig.add_artist(rect)
    n = len(lines)
    for i, (txt, bold) in enumerate(lines):
        fig.text(x + 0.008, y + h - (i + 0.85) * h / (n + 0.3), txt,
                 fontsize=7.5 if not bold else 8.5,
                 fontweight="bold" if bold else "normal", zorder="51" and 51)

def scale_bar(ax, x0, y0, total=10.0, step=2.0):
    """Barre d'échelle alternée noir/blanc."""
    h = 0.35
    n = int(total / step)
    for i in range(n):
        ax.add_patch(Rectangle((x0 + i * step, y0), step, h,
                     facecolor="black" if i % 2 == 0 else "white",
                     edgecolor="black", lw=0.8, zorder=40))
    for i in range(n + 1):
        ax.text(x0 + i * step, y0 - 0.25, f"{int(i*step)}", fontsize=6.5,
                ha="center", va="top", zorder=40)
    ax.text(x0 + total / 2, y0 + h + 0.15, "mètres", fontsize=6.5,
            ha="center", va="bottom", zorder=40)

def _unit(p1, p2):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy) or 1.0
    return dx / L, dy / L, L

def dim(ax, p1, p2, off=0.8, text=None, color=BLEU, fs=7.2, gap=0.12,
        ext=0.18, text_off=0.22, flip_text=False):
    """Cote linéaire entre p1 et p2, décalée de `off` perpendiculairement
    (off>0 : à gauche du vecteur p1->p2). Lignes d'attache + flèches + texte."""
    ux, uy, L = _unit(p1, p2)
    nx, ny = -uy, ux  # normale gauche
    q1 = (p1[0] + nx * off, p1[1] + ny * off)
    q2 = (p2[0] + nx * off, p2[1] + ny * off)
    s = 1 if off >= 0 else -1
    # lignes d'attache (du point vers la ligne de cote, avec petit jeu et dépassement)
    for p, q in ((p1, q1), (p2, q2)):
        a = (p[0] + nx * gap * s, p[1] + ny * gap * s)
        b = (q[0] + nx * ext * s, q[1] + ny * ext * s)
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.55, zorder=20)
    # ligne de cote à double flèche
    ax.add_patch(FancyArrowPatch(q1, q2, arrowstyle="<|-|>", mutation_scale=7,
                                 lw=0.8, color=color, shrinkA=0, shrinkB=0, zorder=21))
    # texte au milieu, orienté le long de la cote
    if text is None:
        text = f"{L:.2f}".replace(".", ",")
    mx, my = (q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang += 180
    toff = text_off if not flip_text else -text_off - 0.1
    ax.text(mx + nx * toff * s, my + ny * toff * s, text, fontsize=fs,
            color=color, ha="center", va="center", rotation=ang,
            rotation_mode="anchor", zorder=22)

def caisson(ax, x, y, w, h, label=None, color=NOIR, fill="#d8dee6",
            uncertain=False, fs=6.2, label_pos="above", angle=0.0):
    """Caisson béton : rectangle (coin bas-gauche x,y) hachuré + étiquette."""
    ec = ORANGE if uncertain else color
    r = Rectangle((x, y), w, h, facecolor=fill, edgecolor=ec, lw=1.0,
                  hatch="////", angle=angle, zorder=15)
    r.set_linestyle("--" if uncertain else "-")
    ax.add_patch(r)
    if label:
        lx, ly, va = x + w / 2, y + h + 0.15, "bottom"
        if label_pos == "below":
            ly, va = y - 0.15, "top"
        elif label_pos == "left":
            lx, ly, va = x - 0.15, y + h / 2, "center"
        elif label_pos == "right":
            lx, ly, va = x + w + 0.15, y + h / 2, "center"
        ax.text(lx, ly, label, fontsize=fs, ha="center", va=va,
                color=ORANGE if uncertain else "#333333", zorder=16,
                fontweight="bold")

def bloc(ax, x, y, w, h, label=None, fs=7):
    r = Rectangle((x, y), w, h, facecolor="#eef1f5", edgecolor=NOIR, lw=1.6,
                  hatch="xx", zorder=14)
    ax.add_patch(r)
    if label:
        ax.text(x + w / 2, y + h / 2, label, fontsize=fs, ha="center",
                va="center", color="#333333", zorder=16, fontweight="bold")

def legende(ax, x, y, items, fs=7):
    dy = 0.62
    for i, (kind, txt) in enumerate(items):
        yy = y - i * dy
        if kind == "caisson":
            ax.add_patch(Rectangle((x, yy - 0.18), 0.85, 0.42, facecolor="#d8dee6",
                         edgecolor=NOIR, hatch="////", lw=0.9, zorder=30))
        elif kind == "caissonU":
            r = Rectangle((x, yy - 0.18), 0.85, 0.42, facecolor="#fff",
                          edgecolor=ORANGE, hatch="////", lw=0.9, zorder=30)
            r.set_linestyle("--")
            ax.add_patch(r)
        elif kind == "bloc":
            ax.add_patch(Rectangle((x, yy - 0.18), 0.85, 0.42, facecolor="#eef1f5",
                         edgecolor=NOIR, hatch="xx", lw=1.1, zorder=30))
        elif kind == "dim":
            ax.add_patch(FancyArrowPatch((x, yy), (x + 0.85, yy), arrowstyle="<|-|>",
                         mutation_scale=6, lw=0.8, color=BLEU, zorder=30))
        elif kind == "dimU":
            ax.add_patch(FancyArrowPatch((x, yy), (x + 0.85, yy), arrowstyle="<|-|>",
                         mutation_scale=6, lw=0.8, color=ORANGE, zorder=30))
        ax.text(x + 1.1, yy, txt, fontsize=fs, va="center", zorder=30)
