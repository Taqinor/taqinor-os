"""Résolution du NOM de ville d'un lead — trois étages de confiance.

Demande fondateur du 07/09/2026 (cas « belksiri » → Mechraa Bel Ksiri) :
Meryem ne corrige plus les villes à la main. Un texte de ville se résout :

① EXACT / VARIANTE CONNUE — la clé normalisée (ou sa forme collée, ou la
   ville en séquence de mots dans un texte d'adresse) est dans le gazetier
   (1 200+ graphies GeoNames) ou le supplément Sahara → nom canonique.
② CONTENANCE UNIQUE — le texte collé est contenu dans (ou contient) la
   forme collée d'EXACTEMENT une ville (« belksiri » ⊂ « mechraabelksiri »)
   → nom canonique. Deux villes candidates ou plus → AMBIGU, jamais un
   choix silencieux.
③ FAUTE DE FRAPPE — similarité ``difflib`` à seuil TRÈS élevé (0.90)
   avec un candidat unique (« casablanka » → Casablanca).

Tout le reste → INCONNU : le texte est laissé TEL QUEL (règle « zéro
chiffre/fait inventé ») ; l'écran « Vérifier la ville » prend le relais.
Chaque statut expose ses candidats pour l'écran.
"""
from __future__ import annotations

import difflib
import math

from .transport_bareme import VILLES_SUPPLEMENT
from .villes_canoniques import VILLES_CANONIQUES
from .villes_maroc import VILLES_MAROC, _normaliser

#: Seuil de similarité « faute de frappe » — TRÈS élevé (0.90, relevé le
#: 07/09 après relecture du dry-run prod : à 0.85, « Said » partait sur
#: Saidia et « mohamed » sur Mohammedia — des PRÉNOMS tapés dans le champ
#: ville). « Oudja »→« oudjda » (0.91) et « El Kelaâ des Sraghna » (0.95)
#: survivent ; en dessous, l'écran carte tranche.
SEUIL_TYPO = 0.90

#: Longueur minimale (collée) pour la contenance : en dessous, « ain » ou
#: « sidi » matcheraient la moitié du pays.
CONTENANCE_MIN = 5

#: Clé → coordonnées, gazetier + supplément Sahara confondus.
_COORDS = dict(VILLES_MAROC)
for _cle, _c in VILLES_SUPPLEMENT.items():
    _COORDS.setdefault(_cle, _c)

_CLES = sorted(_COORDS)
_CLES_COLLEES = {cle: cle.replace(' ', '') for cle in _CLES}


def nom_canonique(cle):
    """Nom d'affichage d'une clé du gazetier (repli : ``title()``)."""
    return VILLES_CANONIQUES.get(cle) or cle.title()


def _resultat(statut, cle=None, candidats=()):
    noms = []
    vues = set()
    for c in candidats:
        coords = _COORDS.get(c)
        if coords in vues:
            continue
        vues.add(coords)
        noms.append(nom_canonique(c))
    return {
        'statut': statut,
        'ville': nom_canonique(cle) if cle else None,
        'coords': _COORDS.get(cle) if cle else None,
        'candidats': noms,
    }


def resoudre_ville(texte):
    """Résout ``texte`` → ``{statut, ville, coords, candidats}``.

    ``statut`` ∈ ``exacte`` (déjà la bonne graphie canonique), ``corrigee``
    (résolue avec confiance — remplacer le texte), ``ambigue`` (2+ villes
    possibles — l'écran décide), ``inconnue`` (rien de sûr — texte conservé).
    """
    cle = _normaliser(texte)
    if not cle:
        return _resultat('inconnue')

    # ① exact / collé.
    direct = None
    if cle in _COORDS:
        direct = cle
    elif cle.replace(' ', '') in _CLES_COLLEES.values():
        colle = cle.replace(' ', '')
        direct = next(c for c, g in _CLES_COLLEES.items() if g == colle)
    if direct is not None:
        statut = ('exacte' if nom_canonique(direct).strip().lower()
                  == str(texte or '').strip().lower() else 'corrigee')
        return _resultat(statut, direct)

    # ①bis — le NOM ENTIER très proche d'une clé AVANT la séquence de mots
    # (cas « El Kelaâ des Sraghna » : GeoNames écrit « Srarhna » ; le
    # scanner de mots matchait l'alias court « el kelaa »… attribué à
    # Kelaat Mgouna, à 300 km — la similarité pleine trouve la bonne ville).
    proches = difflib.get_close_matches(cle, _CLES, n=3, cutoff=SEUIL_TYPO)
    coords = {_COORDS[c] for c in proches}
    if len(coords) == 1:
        return _resultat('corrigee', proches[0])
    if len(coords) > 1:
        return _resultat('ambigue', candidats=proches)

    # ② ville en SÉQUENCE DE MOTS dans un texte (adresse…). TOUS les
    # candidats sont collectés : deux villes différentes dans le même texte
    # (« Skoura Ouarzazate ») ⇒ AMBIGU, jamais la première par ordre
    # alphabétique.
    mots = cle.replace(',', ' ').split()
    trouves = []
    for candidat in sorted(_CLES, key=lambda c: -len(c.split())):
        seq = candidat.split()
        n = len(seq)
        if n > len(mots):
            continue
        if any(mots[i:i + n] == seq for i in range(len(mots) - n + 1)):
            # Un candidat CONTENU dans un déjà-trouvé plus long (même ville
            # ou pas) ne compte pas séparément quand il chevauche : on garde
            # la granularité VILLE via les coordonnées ci-dessous.
            trouves.append(candidat)
    if trouves:
        coords = {_COORDS[c] for c in trouves}
        if len(coords) == 1:
            return _resultat('corrigee', trouves[0])
        return _resultat('ambigue', candidats=trouves)

    # ③ contenance UNIQUE (formes collées, deux sens — « belksiri »).
    colle = cle.replace(' ', '')
    if len(colle) >= CONTENANCE_MIN:
        def _aligne_debut_de_mot(candidat, g):
            # Le fragment doit s'ALIGNER sur un début de mot du candidat
            # (« belksiri » ↔ « [mechraa] bel ksiri ») : à 0.85/milieu de
            # mot, « tanja » tombait dans un alias quelconque d'Oujda.
            mots_c = candidat.split()
            return any(''.join(mots_c[i:]).startswith(colle)
                       for i in range(len(mots_c)))
        contenants = {c for c, g in _CLES_COLLEES.items()
                      if (colle in g and _aligne_debut_de_mot(c, g))
                      or (len(g) >= CONTENANCE_MIN and g in colle)}
        coords = {_COORDS[c] for c in contenants}
        if len(coords) == 1:
            return _resultat('corrigee', sorted(contenants, key=len)[-1])
        if len(coords) > 1:
            return _resultat('ambigue', candidats=sorted(contenants))
    return _resultat('inconnue')


def corriger_ville(texte):
    """Le texte CORRIGÉ à stocker, ou ``texte`` inchangé.

    C'est le point d'entrée des chemins d'écriture (formulaire, webhook,
    sync Odoo) : seule une résolution CONFIANTE remplace ; ambigu/inconnu
    rendent le texte intact — l'écran « Vérifier la ville » s'en charge."""
    resultat = resoudre_ville(texte)
    if resultat['statut'] in ('exacte', 'corrigee') and resultat['ville']:
        return resultat['ville']
    return texte


def _haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2)
         * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def villes_proches(lat, lng, n=8):
    """Les ``n`` villes ERP les plus proches d'un point — pour l'écran
    « Vérifier la ville » (une entrée par ville RÉELLE, pas par graphie)."""
    par_coords = {}
    for cle, coords in _COORDS.items():
        canon = nom_canonique(cle)
        actuel = par_coords.get(coords)
        # Une ville = un jeu de coordonnées ; on garde le nom canonique le
        # plus court (les alias partagent le même canonique de toute façon).
        if actuel is None or len(canon) < len(actuel):
            par_coords[coords] = canon
    lignes = [
        {'ville': nom, 'lat': float(coords[0]), 'lng': float(coords[1]),
         'distance_km': round(_haversine_km((lat, lng), coords), 1)}
        for coords, nom in par_coords.items()
    ]
    lignes.sort(key=lambda x: x['distance_km'])
    return lignes[:n]
