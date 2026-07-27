# -*- coding: utf-8 -*-
"""Résolution des chaînes de cotes du relevé → coordonnées + contrôles de fermeture."""

def chain(start, *segments):
    """Chaîne de cotes 1D : start + segments successifs → liste des positions cumulées.
    chain(0, 1.26, 1.53, 0.64) -> [0, 1.26, 2.79, 3.43]"""
    pos = [start]
    for s in segments:
        pos.append(round(pos[-1] + s, 3))
    return pos

def closure(name, computed, measured, tol=0.30):
    """Contrôle de fermeture : écart chaîne calculée vs cote totale mesurée."""
    ecart = round(computed - measured, 3)
    pct = round(100 * ecart / measured, 2) if measured else 0.0
    ok = abs(ecart) <= tol
    flag = "OK " if ok else "ECART"
    print(f"[{flag}] {name}: somme={computed:.2f} vs mesuré={measured:.2f} "
          f"(résidu {ecart:+.2f} m / {pct:+.1f} %)")
    return ok, ecart

def spread(residual, positions):
    """Répartit un résidu de fermeture au prorata sur les positions intermédiaires
    (compensation de cheminement, comme en topo)."""
    total = positions[-1] - positions[0]
    if total == 0:
        return positions
    return [round(p + residual * (p - positions[0]) / total, 3) for p in positions]
