"""ACAL677 — la surface de la boucle de câblage de chaque chaîne.

Une chaîne est une boucle : les modules dans l'ordre de l'affectation, puis les
deux fils jusqu'au point de collecte du pan (``cheminement.pans.<clé>.
point_collecte``). La surface de cette boucle est une ESTIMATION GÉOMÉTRIQUE
(l'écart réel entre l'aller et le retour n'est pas mesuré) : jamais une
tension induite, jamais un verdict (la limite est ACAL678).

ACAL678 — une LIMITE de surface (réglage société ``boucle_dc_max_m2``, valeur
+ source, vide par défaut) la juge : dépassement = alerte, jamais un blocage ;
sans valeur ou sans source, aucun verdict et le réglage manquant est nommé.

Une surface non calculable vaut ``None`` (jamais 0) et son motif est une phrase
de ``indetermine`` qui nomme le pan et ce qui manque. La fonction ne lève
jamais : ``rejouer_apres_layout`` l'appelle à chaque enregistrement.
"""
from core.calepinage.geo import aire_anneau_m2

from .valeurs import nombre as _nombre

BASE_BOUCLE = (
    "estimation géométrique : centres des modules dans l'ordre de "
    "l'affectation, puis un fil de chaque bout jusqu'au point de collecte ; "
    "l'écart réel entre les deux fils n'est pas mesuré")

#: Arrondi publié de la surface (m²) : la précision d'une estimation faite sur
#: des centres de modules, pas une règle métier.
_ARRONDI_M2 = 1


def _point(brut):
    """``(cx, cy)`` d'un point de collecte ``{cx, cy}``, ou ``None``."""
    if not isinstance(brut, dict):
        return None
    cx, cy = _nombre(brut.get('cx')), _nombre(brut.get('cy'))
    return None if cx is None or cy is None else (cx, cy)


def surface_de_boucle(centres, point_collecte):
    """La surface (m², 0,1 près) du polygone « module 1 … module N, point de
    collecte », ou ``None`` (un seul module, point absent ou illisible)."""
    point = _point(point_collecte)
    if point is None or len(centres or ()) < 2:
        return None
    return round(aire_anneau_m2(list(centres) + [point]), _ARRONDI_M2)


def _centres_du_document(document):
    """``{clé de pan: (centres par numéro stable ou rang, numéros)}``."""
    from .production import cle_de_pan, numeros_des_modules

    zones = (document or {}).get('zones') if isinstance(document, dict) else None
    centres = {}
    for rang, zone in enumerate(zones if isinstance(zones, list) else [],
                                start=1):
        geometrie = (zone or {}).get('geometry') if isinstance(
            zone, dict) else None
        panneaux = (geometrie or {}).get('panels') if isinstance(
            geometrie, dict) else None
        if isinstance(panneaux, list):
            centres[cle_de_pan(zone, rang)] = (
                panneaux, numeros_des_modules(geometrie))
    return centres


def _centre_du_module(module, centres_par_pan):
    """``(clé du pan, (cx, cy) ou None)`` d'une clé ``<pan>#<n>``."""
    cle, _, numero = str(module).rpartition('#')
    panneaux, numeros = centres_par_pan.get(cle, ((), ()))
    try:
        rang = int(numero)
    except ValueError:
        return cle, None
    index = numeros.index(rang) if numeros and rang in numeros else rang - 1
    if not 0 <= index < len(panneaux) or not isinstance(
            panneaux[index], dict):
        return cle, None
    cx, cy = _nombre(panneaux[index].get('cx')), _nombre(
        panneaux[index].get('cy'))
    return cle, (None if cx is None or cy is None else (cx, cy))


#: ACAL678 — le réglage société de la surface maximale d'une boucle (m²).
CLE_LIMITE_BOUCLE = 'boucle_dc_max_m2'


def _m2(valeur):
    return ('%g' % valeur).replace('.', ',')


def _jugee(boucle, limite, source):
    """ACAL678 — la ligne complétée de ``limite_m2``, ``limite_source`` et
    ``depasse`` (``None`` sans limite saisie ou sans surface)."""
    boucle['limite_m2'] = limite
    boucle['limite_source'] = source if limite is not None else None
    surface = boucle['surface_m2']
    boucle['depasse'] = (None if limite is None or surface is None
                         else surface > limite)
    if limite is None:
        boucle['indetermine'].append(
            "limite non saisie : réglage `%s`" % CLE_LIMITE_BOUCLE)
    return boucle


def alertes_de_boucles(boucles):
    """ACAL678 — les phrases d'alerte des boucles au-dessus de la limite."""
    return ["Chaîne %s : boucle de %s m², au-dessus de la limite de %s m² "
            "fixée par la société (source : %s) — rapprochez le point de "
            "collecte du pan." % (boucle['chaine'], _m2(boucle['surface_m2']),
                                  _m2(boucle['limite_m2']),
                                  boucle['limite_source'])
            for boucle in boucles if boucle.get('depasse')]


def boucles_des_chaines(table, document, cheminement, reglages=None):
    """Une ligne par numéro de chaîne de ``table`` (l'affectation), triée.

    ``{chaine, pan, nombre_modules, surface_m2, base, indetermine, limite_m2,
    limite_source, depasse}``. ``reglages`` : la section ``electrique_societe``
    (la limite se lit comme ``seuil_desequilibre_pct`` : sans source, non
    saisie).
    """
    from .raccordement import _reglage

    limite, source = _reglage(reglages, CLE_LIMITE_BOUCLE)
    centres_par_pan = _centres_du_document(document)
    points = ((cheminement or {}).get('pans') if isinstance(
        cheminement, dict) else None) or {}
    par_chaine = {}
    for ligne in table or ():
        if ligne.get('chaine') is not None:
            par_chaine.setdefault(ligne['chaine'], []).append(ligne)
    boucles = []
    for numero, modules in sorted(par_chaine.items()):
        lues = [_centre_du_module(m['module'], centres_par_pan)
                for m in modules]
        cles = list(dict.fromkeys(cle for cle, _centre in lues))
        libelle = ', '.join(dict.fromkeys(m['pan'] for m in modules))
        manque, surface = [], None
        if len(cles) > 1:
            manque.append("chaîne répartie sur %d pans (« %s ») : deux repères "
                          "de pan, surface non mesurable" % (len(cles), libelle))
        elif len(modules) < 2:
            manque.append("pan « %s » : une chaîne d'un seul module ne forme "
                          "pas de boucle mesurable" % libelle)
        elif any(centre is None for _cle, centre in lues):
            manque.append("pan « %s » : centres de modules absents du plan"
                          % libelle)
        elif _point((points.get(cles[0]) or {}).get('point_collecte')
                    if isinstance(points.get(cles[0]), dict) else None) is None:
            manque.append("pan « %s » : point de collecte non saisi"
                          % libelle)
        else:
            surface = surface_de_boucle(
                [centre for _cle, centre in lues],
                points[cles[0]]['point_collecte'])
        boucles.append(_jugee({
            'chaine': numero, 'pan': libelle, 'nombre_modules': len(modules),
            'surface_m2': surface, 'base': BASE_BOUCLE, 'indetermine': manque},
            limite, source))
    return boucles
