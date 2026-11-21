"""ACAL563 — les zones de POSE du toit plat (rive, coin) du ``lestage``.

Quatre paramètres, chacun ``{'valeur', 'source'}``, vides par défaut :
largeur de la bande de rive, largeur de coin, lest additionnel en rive et en
coin. Ils ne peuvent pas entrer dans ``PARAMETRES`` (la feuille les listerait
« manquants » dans la feuille d'aujourd'hui) : ils vivent sous la clé de
structure ``zones_de_pose``. Aucune valeur n'est écrite ici : tout se saisit
avec sa source (CALX361).
"""
from __future__ import annotations

from .parametres import ReglageInvalide

CLE_ZONES_DE_POSE = 'zones_de_pose'

#: clé → (libellé, strictement positif ?). Une largeur est > 0, un lest >= 0.
PARAMETRES_ZONES_DE_POSE = {
    'largeur_bande_rive_m': ("Largeur de la bande de rive (m)", True),
    'largeur_coin_m': ("Largeur de coin (m)", True),
    'lest_rive_kg_par_module': (
        "Lest additionnel en rive (kg par module)", False),
    'lest_coin_kg_par_module': (
        "Lest additionnel en coin (kg par module)", False),
}


def _refus(message, champ):
    return ReglageInvalide(message, champ=champ)


def normaliser_zones_de_pose(valeur):
    """``zones_de_pose`` VALIDÉE — ``{}`` si rien n'est saisi.

    Raises:
        ReglageInvalide: message français nommant ``zones_de_pose.<clé>``.
    """
    if valeur is None or valeur == {}:
        return {}
    if not isinstance(valeur, dict):
        raise _refus(
            "Les zones de pose se saisissent en objet "
            f"(reçu : {type(valeur).__name__}).", CLE_ZONES_DE_POSE)
    inconnues = sorted(set(valeur) - set(PARAMETRES_ZONES_DE_POSE))
    if inconnues:
        raise _refus(
            f"Zones de pose : clé inconnue « {inconnues[0]} ». Admises : "
            f"{', '.join(PARAMETRES_ZONES_DE_POSE)}.",
            f'{CLE_ZONES_DE_POSE}.{inconnues[0]}')
    propre = {}
    for cle, brut in valeur.items():
        if brut is None:
            continue
        libelle, strict = PARAMETRES_ZONES_DE_POSE[cle]
        champ = f'{CLE_ZONES_DE_POSE}.{cle}'
        if not isinstance(brut, dict):
            raise _refus(
                f"« {libelle} » se saisit avec sa source : "
                '{"valeur": …, "source": "référence du texte"}.', champ)
        surplus = sorted(set(brut) - {'valeur', 'source'})
        if surplus:
            raise _refus(
                f"« {libelle} » n'accepte que « valeur » et « source » "
                f"(reçu en plus : {', '.join(surplus)}).", champ)
        source = brut.get('source')
        if not isinstance(source, str) or not source.strip():
            raise _refus(
                f"« {libelle} » doit porter la RÉFÉRENCE du texte d'où elle "
                "vient : aucune valeur n'est admise sans sa source.", champ)
        nombre = brut.get('valeur')
        if isinstance(nombre, bool) or not isinstance(nombre, (int, float)):
            raise _refus(
                f"« {libelle} » doit être un nombre "
                f"(reçu : {type(nombre).__name__}).", champ)
        if float(nombre) < 0 or (strict and float(nombre) == 0):
            raise _refus(
                f"« {libelle} » doit être "
                + ("supérieure à zéro" if strict else "positif ou nul")
                + f" (reçu : {nombre}).", champ)
        propre[cle] = {'valeur': float(nombre), 'source': source.strip()}
    return propre


# ── ACAL564 — chaque module rangé en centre, rive ou coin ───────────────────

def _distance_segment(point, a, b):
    """Distance (m) de ``point`` au segment ``[a, b]``."""
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    longueur2 = dx * dx + dy * dy
    t = 0 if longueur2 == 0 else max(0, min(1, (
        (px - ax) * dx + (py - ay) * dy) / longueur2))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def _zone_du_module(centre, points, bande, coin):
    """« coin » près d'un SOMMET, sinon « rive » près d'une arête, sinon
    « centre » — bornes INCLUSES."""
    if any(_distance_segment(centre, s, s) <= coin for s in points):
        return 'coin'
    aretes = zip(points, points[1:] + points[:1])
    if any(_distance_segment(centre, a, b) <= bande for a, b in aretes):
        return 'rive'
    return 'centre'


def repartir_modules(pans, zones_de_pose):
    """Lecture PURE : les modules des pans de TOIT classés par zone de pose,
    avec le lest ADDITIONNEL saisi pour leur zone (0 au centre, par
    définition). Un paramètre non saisi ⇒ ``disponible: False`` et
    ``manquants`` le nomme — jamais une largeur de repli. Aucun montant."""
    zones_de_pose = zones_de_pose or {}
    manquants = [{'cle': cle, 'libelle': libelle}
                 for cle, (libelle, _strict) in PARAMETRES_ZONES_DE_POSE.items()
                 if not isinstance(zones_de_pose.get(cle), dict)
                 or zones_de_pose[cle].get('valeur') is None]
    if manquants:
        return {'disponible': False, 'pans': [], 'total_lest_kg': None,
                'manquants': manquants}
    val = {cle: float(zones_de_pose[cle]['valeur'])
           for cle in PARAMETRES_ZONES_DE_POSE}
    lest = {'centre': 0.0, 'rive': val['lest_rive_kg_par_module'],
            'coin': val['lest_coin_kg_par_module']}
    sortie = []
    for pan in pans or []:
        points = [tuple(p) for p in pan.get('points') or []]
        if len(points) < 2 + 1 or not pan.get('modules'):
            continue
        modules = []
        for centre in pan['modules']:
            zone = _zone_du_module(tuple(centre), points,
                                   val['largeur_bande_rive_m'],
                                   val['largeur_coin_m'])
            modules.append({'centre': list(centre), 'zone': zone,
                            'lest_kg': lest[zone]})
        compte = {z: sum(1 for m in modules if m['zone'] == z)
                  for z in ('centre', 'rive', 'coin')}
        sortie.append({
            'pan': pan.get('repere'), 'centres': compte['centre'],
            'rives': compte['rive'], 'coins': compte['coin'],
            'lest_kg': sum(m['lest_kg'] for m in modules),
            'modules': modules})
    return {'disponible': True, 'pans': sortie,
            'total_lest_kg': sum(p['lest_kg'] for p in sortie),
            'manquants': []}


def repartition_du_lestage(calepinage):
    """La répartition du calepinage : la géométrie STOCKÉE
    (``planche.geometrie_de_planche``, pans de toit seulement — surfaces au
    sol et ombrières hors périmètre) et les ``zones_de_pose`` de la société."""
    from ..selectors import parametres_de_societe
    from .planche import PlancheRefusee, geometrie_de_planche

    section = (parametres_de_societe(getattr(calepinage, 'company', None))
               or {}).get('lestage') or {}
    try:
        pans = geometrie_de_planche(calepinage.roof_layout).get('pans') or []
    except PlancheRefusee:
        pans = []
    return repartir_modules(pans, section.get(CLE_ZONES_DE_POSE))
