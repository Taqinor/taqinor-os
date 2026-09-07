"""Barème de transport par ville — départ Nouaceur (fondateur, 07/09/2026).

Reda a fixé cinq prix HT (les ANCRES) : Rabat 1 200, Kénitra 1 500,
Marrakech 1 500, Fès 2 000, Tanger 2 000. Toute autre ville est DÉRIVÉE de
ces ancres — jamais un chiffre inventé :

* distance à vol d'oiseau Nouaceur → ville (coordonnées GeoNames du
  gazetier ``villes_maroc`` ; le détour routier est absorbé par le
  calibrage, la courbe passant exactement par les cinq prix fondateur) ;
* interpolation LINÉAIRE entre deux ancres ; au-delà de Tanger,
  extrapolation à la pente moyenne Rabat → Tanger (≈ 3,77 MAD/km) ; en
  deçà de Rabat, plancher 800 HT à Nouaceur (validé fondateur 07/09/2026,
  « yes for both ») qui monte linéairement vers Rabat ;
* arrondi aux 50 MAD SUPÉRIEURS. Aux ancres, la formule rend exactement
  le prix fondateur (ce sont ses nœuds).

Le gazetier ne couvre pas les villes du Sahara (GeoNames les range sous le
code pays EH) : un petit supplément de coordonnées GeoNames VERBATIM les
ajoute (Laâyoune, Dakhla, Boujdour…).

Une ville inconnue rend ``None`` — le consommateur garde alors le prix
catalogue de la ligne Transport, jamais un prix deviné.
"""
from __future__ import annotations

import math

from .villes_maroc import VILLES_MAROC, _normaliser, coordonnees_ville

#: Départ des marchandises — Nouaceur (GeoNames « Zawyat an Nwaçer »).
ORIGINE_NOUACEUR = (33.3798, -7.6193)

#: Les cinq prix fondateur (clé gazetier → MAD HT).
ANCRES_HT = (
    ('rabat', 1200),
    ('kenitra', 1500),
    ('marrakech', 1500),
    ('fes', 2000),
    ('tanger', 2000),
)

#: Plancher de la zone proche (Nouaceur même) — validé fondateur 07/09/2026.
PLANCHER_HT = 800

#: Arrondi commercial : aux 50 MAD supérieurs.
ARRONDI_MAD = 50

#: Villes du Sahara absentes du gazetier (export GeoNames EH, coordonnées
#: VERBATIM, lieux habités >= 5 000 hab. + chefs-lieux).
VILLES_SUPPLEMENT = {
    'laayoune': (27.1418, -13.188),
    'el aaiun': (27.1418, -13.188),
    'dakhla': (23.6848, -15.958),
    'ad dakhla': (23.6848, -15.958),
    'boujdour': (26.1307, -14.4851),
    'bojador': (26.1307, -14.4851),
    'el marsa': (27.0961, -13.4158),
    'tichla': (21.5837, -14.9722),
    'el aargub': (23.6088, -15.8673),
    'meharrize': (26.1476, -11.0693),
    'bir ghandouz': (22.0532, -16.7484),
}


def _haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2)
         * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


#: Nœuds (distance_km, prix_ht) calculés UNE fois depuis le gazetier — la
#: même source que la résolution des villes, pour que les ancres rendent
#: exactement leur prix.
_NOEUDS = tuple(sorted(
    (_haversine_km(ORIGINE_NOUACEUR, VILLES_MAROC[cle]), prix)
    for cle, prix in ANCRES_HT))

#: Pente d'extrapolation au-delà de la dernière ancre (MAD/km) : la pente
#: moyenne première ancre → dernière ancre des prix fondateur eux-mêmes.
_PENTE = ((_NOEUDS[-1][1] - _NOEUDS[0][1])
          / (_NOEUDS[-1][0] - _NOEUDS[0][0]))


def _coordonnees(texte):
    """Coordonnées de la ville nommée dans ``texte``.

    Le SUPPLÉMENT Sahara passe AVANT le gazetier : le gazetier (dump MA)
    contient un quartier d'Agadir nommé « Dakhla » — sans cette priorité,
    un client de la vraie Dakhla (1 350 km) serait tarifé comme Agadir."""
    cle = _normaliser(texte)
    if not cle:
        return None
    exact = VILLES_SUPPLEMENT.get(cle)
    if exact:
        return exact
    coords = coordonnees_ville(texte)
    if coords:
        return coords
    mots = cle.replace(',', ' ').split()
    for candidat in sorted(VILLES_SUPPLEMENT, key=lambda c: -len(c.split())):
        seq = candidat.split()
        n = len(seq)
        for i in range(len(mots) - n + 1):
            if mots[i:i + n] == seq:
                return VILLES_SUPPLEMENT[candidat]
    return None


def prix_transport_ht_pour_distance(distance_km):
    """MAD HT pour une distance à vol d'oiseau depuis Nouaceur (>= 0)."""
    d_min, p_min = _NOEUDS[0]
    d_max, p_max = _NOEUDS[-1]
    if distance_km <= d_min:
        brut = PLANCHER_HT + (p_min - PLANCHER_HT) * (distance_km / d_min)
    elif distance_km >= d_max:
        brut = p_max + _PENTE * (distance_km - d_max)
    else:
        brut = p_max
        for (d1, p1), (d2, p2) in zip(_NOEUDS, _NOEUDS[1:]):
            if d1 <= distance_km <= d2:
                brut = p1 + (p2 - p1) * (distance_km - d1) / (d2 - d1)
                break
    return int(math.ceil(brut / ARRONDI_MAD) * ARRONDI_MAD)


def prix_transport_ht(ville):
    """MAD HT du transport vers ``ville`` (texte libre), ou ``None``.

    ``None`` = ville non reconnue : l'appelant GARDE son prix par défaut
    (le prix catalogue de la ligne Transport), jamais un prix deviné.
    """
    coords = _coordonnees(ville)
    if coords is None:
        return None
    return prix_transport_ht_pour_distance(
        _haversine_km(ORIGINE_NOUACEUR, coords))


def prix_transport_ttc(ville, taux_tva=20):
    """MAD TTC (arrondi au dirham) — TVA 20 % par défaut."""
    ht = prix_transport_ht(ville)
    if ht is None:
        return None
    return int(round(ht * (1 + float(taux_tva) / 100)))
