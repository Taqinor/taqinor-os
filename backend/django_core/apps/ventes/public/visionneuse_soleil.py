"""D-ACAL-132 (fondateur, 26/11/2026) — clé publique ADDITIVE ``visionneuse_soleil``.

Un lien de niveau « confiance » montre la visionneuse au soleil qui bouge de
l'écran Panneaux du calepinage : la page anime le soleil elle-même (même
fonction que l'atelier) ; le serveur ne lui sert que ce que l'atelier a
ENREGISTRÉ. Contrat : ``apps/ventes/contract_samples/visionneuse_soleil.json``
(jumeau ``apps/web/src/contract_samples/``) ; conception :
``docs/audits/l5-calepinage/visionneuse-soleil-client.md`` ; décisions
D-ACAL-132 à D-ACAL-138.

* ``zones`` — l'accès solaire par module ENREGISTRÉ par le calepinage
  (``zones[].geometry.solarAccess.values``), lu par le SEUL lecteur du
  calepinage (``apps.calepinage.selectors.acces_solaire_par_module``) :
  jamais un second calcul d'ombrage. Réaligné sur les panneaux GARDÉS par
  ``public_views._safe_zone_geometry`` (même filtre, même plafond) ; un pan
  dont le nombre de valeurs diffère de son nombre de modules est OMIS en bloc
  (jamais complété, jamais réaligné au hasard) — D-ACAL-136.
* ``environnement`` — les objets voisins à hauteur saisie, GÉOMÉTRIE seule :
  jamais leur ``id`` ni leur ``label`` (texte libre), jamais un objet
  « supposé coupé » — D-ACAL-137.
* ``instant_choisi`` — l'instant de scène choisi par le commercial, ``None``
  au défaut de l'atelier (même règle que ``instantSoleilChoisi``) — D-ACAL-135.

Lecture pure (rien n'est écrit, aucune empreinte lue ni recalculée) ;
best-effort : ne lève jamais, une erreur rend ``None`` (clé absente).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

VERSION = 1
#: Défaut de scène de l'atelier : jour 355, midi (``vueClient.helpers.js``).
INSTANT_PAR_DEFAUT = (355.0, 12.0)
#: Plafond d'objets voisins republiés (taille de la charge publique).
MAX_OBJETS_VOISINS = 200
#: Les clés propres à chaque genre d'objet voisin (``environment.ts``).
_EXTRAS_PAR_GENRE = {
    'arbre': ('crownDiameterM',),
    'batiment': ('lengthM', 'widthM'),
    'poteau': ('diameterM',),
    'ligne': ('epaisseurM',),
}
_TRACES_PAR_GENRE = {'batiment': 'footprint', 'ligne': 'trace'}


def visionneuse_soleil_publique(devis, layout_public, niveau):
    """La clé ``visionneuse_soleil``, ou ``None`` (clé ABSENTE).

    ``None`` hors niveau « confiance » et quand ``layout_public`` (le
    ``roof_layout`` réellement servi) est vide : la case « Calepinage 3D »
    décochée, un brouillon en conception rapide ou un devis sans calepinage
    gardent la page d'aujourd'hui."""
    from ..models import ShareLink

    if niveau != ShareLink.NIVEAU_CONFIANCE or not layout_public:
        return None
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return None
    try:
        return {
            'version': VERSION,
            'zones': _zones_tintees(layout, layout_public),
            'environnement': _environnement(layout.get('environment')),
            'instant_choisi': _instant_choisi(layout.get('scene')),
        }
    except Exception:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
        logger.warning('visionneuse_soleil indisponible (devis %s)',
                       getattr(devis, 'pk', None), exc_info=True)
        return None


def _reperes_uniques(zones):
    """Les repères (``label``/``id``) portés par UN SEUL pan : le lecteur du
    calepinage indexe par repère, deux pans au même repère se masquent."""
    porteurs = {}
    for rang, zone in enumerate(zones):
        for repere in (zone.get('label'), zone.get('id')):
            if repere:  # même lecture que ``acces_par_module``
                porteurs.setdefault(str(repere), set()).add(rang)
    return {repere for repere, rangs in porteurs.items() if len(rangs) == 1}


def _zones_tintees(layout, layout_public):
    """Un élément par pan SERVI dont le document porte un accès exploitable."""
    from apps.calepinage.selectors import acces_solaire_par_module

    from ..public_views import _MAX_PANNEAUX_PUBLIES, _nombre_publiable

    brutes = [z for z in layout.get('zones') or () if isinstance(z, dict)]
    servies = layout_public.get('zones') or []
    if len(brutes) != len(servies):
        return []
    par_pan = acces_solaire_par_module(layout)
    uniques = _reperes_uniques(brutes)
    sortie = []
    for index, (zone, servie) in enumerate(zip(brutes, servies)):
        identifiant = zone.get('id')
        if not isinstance(identifiant, str) or identifiant not in uniques \
                or servie.get('id') != identifiant:
            continue
        geometrie = zone.get('geometry')
        geometrie = geometrie if isinstance(geometrie, dict) else {}
        panneaux = geometrie.get('panels')
        valeurs = par_pan.get(identifiant)
        if not isinstance(panneaux, list) or not isinstance(valeurs, list) \
                or len(valeurs) != len(panneaux):
            continue
        acces = [_facteur(valeurs[rang])
                 for rang, cellule in enumerate(panneaux[:_MAX_PANNEAUX_PUBLIES])
                 if isinstance(cellule, dict)
                 and _nombre_publiable(cellule.get('cx')) is not None
                 and _nombre_publiable(cellule.get('cy')) is not None]
        publies = (servie.get('geometry') or {}).get('panels') or []
        if len(acces) != len(publies) or all(a is None for a in acces):
            continue
        sortie.append({'index': index, 'id': identifiant, 'acces': acces,
                       'calcule_le': _horodatage(geometrie.get('solarAccess'))})
    return sortie


def _facteur(valeur):
    """Un facteur d'accès dans [0 ; 1] au millième, ou ``None`` (non calculé,
    ou illisible : jamais corrigé, jamais 1)."""
    if valeur is None or isinstance(valeur, bool) or not 0 <= valeur <= 1:
        return None
    return round(float(valeur), 3)


def _horodatage(acces):
    """``solarAccess.computedAt`` (chaîne ISO 8601 courte), sinon ``None``."""
    from ..public_views import _texte_publiable

    return (_texte_publiable(acces.get('computedAt'))
            if isinstance(acces, dict) else None)


def _environnement(brut):
    """Les objets voisins qui portent une ombre, géométrie seule."""
    from ..public_views import _couples_publiables, _nombre_publiable

    sortie = []
    for objet in (brut if isinstance(brut, list) else [])[:MAX_OBJETS_VOISINS]:
        if not isinstance(objet, dict) or objet.get('supposeCoupe') is True:
            continue
        genre = objet.get('kind')
        lng, lat, hauteur = (_nombre_publiable(objet.get(cle))
                             for cle in ('centerLng', 'centerLat', 'heightM'))
        if genre not in _EXTRAS_PAR_GENRE or lng is None or lat is None \
                or hauteur is None or hauteur <= 0:
            continue
        sorti = {'kind': genre, 'centerLng': lng, 'centerLat': lat,
                 'heightM': hauteur}
        for cle in _EXTRAS_PAR_GENRE[genre]:
            dimension = _nombre_publiable(objet.get(cle))
            if dimension is not None and dimension > 0:
                sorti[cle] = dimension
        if genre == 'arbre' and isinstance(objet.get('evergreen'), bool):
            sorti['evergreen'] = objet['evergreen']
        trace = _TRACES_PAR_GENRE.get(genre)
        if trace and (sommets := _couples_publiables(objet.get(trace))):
            sorti[trace] = sommets
        sortie.append(sorti)
    return sortie


def _instant_choisi(scene):
    """``{jour, heure}`` choisi par le commercial, ``None`` au défaut (355, 12)
    ou quand l'instant enregistré est illisible ou hors bornes."""
    from ..public_views import _nombre_publiable

    if not isinstance(scene, dict):
        return None
    jour = _nombre_publiable(scene.get('sunDay'))
    heure = _nombre_publiable(scene.get('sunHour'))
    if jour is None or heure is None or (jour, heure) == INSTANT_PAR_DEFAUT \
            or not jour.is_integer() or not 1 <= jour <= 366 or not 0 <= heure <= 24:
        return None
    return {'jour': int(jour),
            'heure': int(heure) if heure.is_integer() else heure}
