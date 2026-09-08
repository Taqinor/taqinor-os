"""Lieux-dits du Maroc — douars, quartiers, hameaux (GeoNames, ~47 000 lieux).

VREF-LIEUX (fondateur 08/09/2026, cas « Sidi Hashass ») : le gazetier des
VILLES (``villes_maroc``, 409 entrées) ignore les douars par construction, et
Nominatim (OpenStreetMap) n'en connaît qu'une minorité — Google, lui, place
« Sidi Hashass » (سيدي حسحاس) à 3 km de Madagh. GeoNames recense pourtant
~47 000 lieux habités du Maroc (classe ``P``) : ce module les charge
PARESSEUSEMENT depuis ``data/lieux_maroc.tsv.gz`` (généré par
``scripts/build_lieux_maroc.py``, licence CC-BY 4.0) et rend la position d'un
lieu-dit nommé dans un texte — UNIQUEMENT quand la correspondance est sans
équivoque :

* le texte ENTIER est un lieu-dit (préfixe « douar/dchar » toléré), au mot
  près ou à une faute de frappe près (seuil 0,90, le même que
  ``villes_resolution``, sur 8 caractères collés au moins) ;
* à défaut, pour un texte d'ADRESSE (3 mots et plus), un lieu-dit cité en
  entier dans le texte — mais alors seulement CORROBORÉ par une ville de
  contexte (la ville du lead, ou une ville du gazetier citée dans le texte)
  à moins de 60 km : un morceau d'adresse seul ne suffit jamais ;
* homonymes (« Oulad Ali » existe 50 fois) : la ville de contexte départage ;
  s'il reste des candidats à plus de 5 km les uns des autres → AMBIGU →
  ``None``, jamais un choix silencieux (règle « zéro fait inventé ») —
  l'écran carte laisse alors Meryem cliquer ;
* une VILLE du gazetier n'est jamais rendue ici : l'étage « ville » de
  l'appelant l'annonce sous sa propre précision.

Coordonnées GeoNames VERBATIM ; l'appelant annonce la précision
``'lieu-dit'`` (le centre d'un douar, jamais le toit du client).
"""
from __future__ import annotations

import difflib
import gzip
import math
from functools import lru_cache
from pathlib import Path

from .transport_bareme import VILLES_SUPPLEMENT
from .villes_maroc import VILLES_MAROC, _normaliser, coordonnees_ville

FICHIER = Path(__file__).resolve().parent / 'data' / 'lieux_maroc.tsv.gz'

#: Seuil « faute de frappe » — aligné sur ``villes_resolution.SEUIL_TYPO``.
SEUIL_TYPO = 0.90
#: Longueur COLLÉE minimale pour tolérer une faute : en dessous, une lettre
#: d'écart pèse plus de 10 % et le seuil n'a plus de sens.
LONGUEUR_MIN_TYPO = 8
#: Deux entrées à ≤ 5 km = le même lieu (le douar et son quartier GeoNames).
RAYON_GROUPE_KM = 5.0
#: Un lieu-dit n'est retenu qu'à ≤ 60 km de la ville de contexte.
RAYON_CONTEXTE_KM = 60.0
#: Préfixes génériques tolérés (« douar sidi hashass » = « sidi hashass »).
PREFIXES = ('douar ', 'dchar ', 'dawar ', 'douwar ', 'dcher ')
#: Mots d'adresse génériques : jamais un lieu-dit à eux seuls.
STOPLIST = {
    'centre', 'centre ville', 'ville', 'medina', 'quartier', 'hay',
    'lotissement', 'residence', 'immeuble', 'rue', 'avenue', 'boulevard',
    'route', 'gare', 'plage', 'marina', 'corniche', 'maroc', 'morocco',
    'douar', 'dchar', 'nouvelle ville', 'ville nouvelle',
}

#: Coordonnées (arrondies) des VILLES du gazetier : un lieu-dit qui y tombe
#: EST une ville — rendu par l'étage « ville », pas par celui-ci.
_VILLES_COORDS = {
    (round(float(lat), 4), round(float(lng), 4))
    for lat, lng in list(VILLES_MAROC.values()) + list(VILLES_SUPPLEMENT.values())
}


def _sans_prefixe(cle):
    for prefixe in PREFIXES:
        if cle.startswith(prefixe) and len(cle) - len(prefixe) >= 4:
            return cle[len(prefixe):]
    return cle


def _haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2)
         * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


@lru_cache(maxsize=1)
def _index():
    """(entrées, exact, collé) — construit UNE fois par processus.

    ``entrées`` : liste de ``(nom, lat, lng)`` ; ``exact`` : clé normalisée
    (nom, alternates, variantes sans préfixe) → ids ; ``collé`` : 3 premières
    lettres de la clé collée → {clé collée → ids} (seaux de la recherche
    « faute de frappe »)."""
    entrees, exact, colle = [], {}, {}
    if not FICHIER.exists():
        return entrees, exact, colle
    with gzip.open(FICHIER, 'rt', encoding='utf-8') as fh:
        for ligne in fh:
            if not ligne.strip() or ligne.startswith('#'):
                continue
            cols = ligne.rstrip('\n').split('\t')
            if len(cols) < 3:
                continue
            try:
                lat, lng = float(cols[1]), float(cols[2])
            except ValueError:
                continue
            idx = len(entrees)
            entrees.append((cols[0], lat, lng))
            graphies = [cols[0]]
            if len(cols) > 4 and cols[4]:
                graphies += cols[4].split(',')
            for graphie in graphies:
                cle = _normaliser(graphie)
                if not cle:
                    continue
                for variante in {cle, _sans_prefixe(cle)}:
                    exact.setdefault(variante, set()).add(idx)
                    collee = variante.replace(' ', '')
                    if len(collee) >= LONGUEUR_MIN_TYPO:
                        (colle.setdefault(collee[:3], {})
                              .setdefault(collee, set()).add(idx))
    return entrees, exact, colle


def _ids_exacts(cle, exact):
    ids = set()
    for variante in {cle, _sans_prefixe(cle)}:
        ids |= exact.get(variante, set())
    return ids


def _ids_typo(cle, colle):
    ids = set()
    for variante in {cle, _sans_prefixe(cle)}:
        collee = variante.replace(' ', '')
        if len(collee) < LONGUEUR_MIN_TYPO:
            continue
        seau = colle.get(collee[:3]) or {}
        for proche in difflib.get_close_matches(
                collee, list(seau), n=8, cutoff=SEUIL_TYPO):
            ids |= seau[proche]
    return ids


def _ids_fenetres(cle, exact, colle):
    """Lieux-dits cités en entier (fenêtres de 2 à 4 mots) dans un texte
    d'adresse d'au moins 3 mots."""
    mots = cle.split()
    ids = set()
    if len(mots) < 3:
        return ids
    for taille in (4, 3, 2):
        for debut in range(0, len(mots) - taille + 1):
            fenetre = ' '.join(mots[debut:debut + taille])
            if fenetre in STOPLIST or _sans_prefixe(fenetre) in STOPLIST:
                continue
            ids |= _ids_exacts(fenetre, exact) or _ids_typo(fenetre, colle)
    return ids


def _regroupes(candidats):
    """Vrai si tous les candidats sont à ≤ RAYON_GROUPE_KM les uns des autres."""
    for a in candidats:
        for b in candidats:
            if _haversine_km((a[1], a[2]), (b[1], b[2])) > RAYON_GROUPE_KM:
                return False
    return True


def position_lieu_dit(texte, contexte_ville=''):
    """``(lat, lng, nom)`` du lieu-dit nommé dans ``texte``, ou ``None``.

    ``contexte_ville`` : la ville du lead (ou vide) — elle départage les
    homonymes et CORROBORE tout lieu-dit trouvé dans un morceau d'adresse."""
    cle = _normaliser(texte)
    if len(cle) < 4 or cle in STOPLIST or _sans_prefixe(cle) in STOPLIST:
        return None
    entrees, exact, colle = _index()
    if not entrees:
        return None
    ids = _ids_exacts(cle, exact) or _ids_typo(cle, colle)
    par_fenetre = False
    if not ids:
        ids = _ids_fenetres(cle, exact, colle)
        par_fenetre = True
    if not ids:
        return None
    ancre = coordonnees_ville(contexte_ville) if contexte_ville else None
    if ancre is None:
        # Une ville du gazetier citée DANS le texte (« … route de Madagh »).
        ancre = coordonnees_ville(cle)
    candidats = [entrees[i] for i in ids]
    if ancre is not None:
        candidats = [
            c for c in candidats
            if _haversine_km((float(ancre[0]), float(ancre[1])),
                             (c[1], c[2])) <= RAYON_CONTEXTE_KM]
        if not candidats:
            return None
    elif par_fenetre:
        return None  # un morceau d'adresse sans ville de contexte : pas assez sûr
    if not _regroupes(candidats):
        return None  # homonymes éloignés : ambigu, jamais un choix silencieux
    nom, lat, lng = min(candidats, key=lambda c: (len(c[0]), c[0]))
    if (round(lat, 4), round(lng, 4)) in _VILLES_COORDS:
        return None  # c'est une VILLE du gazetier : l'étage « ville » l'annonce
    return (lat, lng, nom)
