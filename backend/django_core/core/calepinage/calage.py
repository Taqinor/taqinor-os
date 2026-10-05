# -*- coding: utf-8 -*-
"""ACAL202 — LE validateur unique d'un calage à quatre coins (drapage d'une photo).

LE CONSTAT (C-ACAL-020/021)
---------------------------
Deux copies du même contrôle vivaient côté serveur — ``apps.visites``
(``VisiteTerrainViewSet.calage``, VT11) et ``apps.calepinage``
(``services.photos.calage_photo_site``, CAL53) — et aucune ne refusait un
quadrilatère DÉGÉNÉRÉ : quatre coins confondus, alignés ou croisés (« nœud
papillon ») passaient, puis le drapage de la photo s'effondrait à l'écran.

LA RÈGLE (une seule, ici)
-------------------------
Un calage est ``{"coins": [[lat, lng] × 4]}`` dont les quatre coins, pris dans
l'ordre, forment un quadrilatère SIMPLE, CONVEXE et d'aire non nulle — la seule
forme qu'une homographie de photo sait draper. Le contrôle se fait dans le plan
(lng, lat) : à l'échelle d'un toit, la courbure terrestre est sans effet sur le
signe des produits vectoriels.

Paquet PUR (``core.calepinage``) : stdlib seule, aucune app importée — les deux
apps l'importent sans dépendre l'une de l'autre.
"""
from __future__ import annotations

import math

from core.calepinage.exceptions import EntreeInvalide

__all__ = ["CalageInvalide", "valider_quatre_coins"]

#: En dessous de ce produit vectoriel (degrés²), deux côtés consécutifs sont
#: tenus pour alignés. 1e-14 deg² ≈ un côté de 1 cm contre un côté de 1 m :
#: bien sous toute photo réelle, bien au-dessus du bruit flottant.
EPSILON_PRODUIT = 1e-14


class CalageInvalide(EntreeInvalide):
    """Le calage est refusé — message français, champ nommé par l'appelant."""


def _nombre(valeur):
    if isinstance(valeur, bool):
        raise CalageInvalide(
            "Coordonnée de calage invalide (latitude/longitude attendues).")
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise CalageInvalide(
            "Coordonnée de calage invalide (latitude/longitude "
            "attendues).") from None
    if not math.isfinite(nombre):
        raise CalageInvalide(
            "Coordonnée de calage invalide (latitude/longitude attendues).")
    return nombre


def valider_quatre_coins(calage):
    """Rend le calage NORMALISÉ ``{"coins": [[lat, lng] × 4]}`` ou refuse.

    Args:
        calage: l'objet reçu (``{"coins": [...]}``). ``None`` n'est PAS traité
            ici : « effacer » est une décision de l'appelant.

    Raises:
        CalageInvalide: objet absent/non objet, pas exactement 4 coins, coin
            qui n'est pas une paire, coordonnée illisible ou hors amplitude
            GPS, coins confondus, alignés ou croisés (quadrilatère dégénéré).
    """
    coins = calage.get("coins") if isinstance(calage, dict) else None
    if not isinstance(coins, (list, tuple)) or len(coins) != 4:
        raise CalageInvalide(
            "Le calage attend exactement 4 coins [latitude, longitude].")

    propres = []
    for coin in coins:
        if not isinstance(coin, (list, tuple)) or len(coin) != 2:
            raise CalageInvalide(
                "Chaque coin doit être une paire [latitude, longitude].")
        lat, lng = _nombre(coin[0]), _nombre(coin[1])
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise CalageInvalide("Coordonnée de calage hors amplitude GPS.")
        propres.append([lat, lng])

    if len({(lat, lng) for lat, lng in propres}) != 4:
        raise CalageInvalide(
            "Calage dégénéré : deux coins sont confondus — placez les quatre "
            "coins sur quatre points distincts.")

    # Produit vectoriel de chaque paire de côtés consécutifs (plan lng, lat).
    signes = []
    for i in range(4):
        a, b, c = propres[i], propres[(i + 1) % 4], propres[(i + 2) % 4]
        ux, uy = b[1] - a[1], b[0] - a[0]
        vx, vy = c[1] - b[1], c[0] - b[0]
        produit = ux * vy - uy * vx
        if abs(produit) <= EPSILON_PRODUIT:
            raise CalageInvalide(
                "Calage dégénéré : trois coins sont alignés — le "
                "quadrilatère n'a pas de surface.")
        signes.append(produit > 0)
    if len(set(signes)) != 1:
        raise CalageInvalide(
            "Calage dégénéré : les coins se croisent ou le quadrilatère "
            "n'est pas convexe — replacez les coins dans l'ordre du tour.")
    return {"coins": propres}
