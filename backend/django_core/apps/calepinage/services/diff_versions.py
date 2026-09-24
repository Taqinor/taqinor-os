"""CALX345 — le DIFFÉRENTIEL champ par champ entre deux versions.

LE CONSTAT
----------
``services/versions.py`` gèle des instantanés ENTIERS (``CalepinageVersion``)
sans jamais les confronter, et ``services/journal.py`` ne note que l'ancien et
le nouveau nombre de modules : comparer deux versions obligeait à diffuser
deux blocs JSON complets au navigateur. Parité : PV*SOL compare l'état du
projet ET ses résultats (https://help.valentin-software.com/pvsol/en/
project-comparison/) ; HelioScope bascule une métrique « for quick
comparison between simulations ».

LES GRANDEURS COMPARÉES — une liste FERMÉE, jamais un diff de JSON brut
------------------------------------------------------------------------
Lues dans le DOCUMENT ``roof_layout`` (schéma v2) de chaque côté, sans rien
recalculer : nombre de modules (``result.panels``, à défaut les cellules
``zones[].geometry.panels`` réellement posées), kWc (``result.kwc``), nombre
de pans (``zones``), nombre d'obstacles (``zones[].obstacles``), orientation
et inclinaison PAR PAN (``geometry.azimuthDeg``/``tiltDeg``, à défaut
``facingAzimuthDeg``/``pitchDeg`` — même lecture que ``planche.py``), puis
l'empreinte du layout et la version du moteur. La forme publiée est celle du
contrat ``contract_samples/calepinage_versions_diff.json`` (CALX333).

TROIS RÈGLES
------------
* une grandeur ÉGALE des deux côtés n'est pas un écart (deux versions
  identiques ⇒ ``ecarts: []``) ;
* un champ ABSENT des deux côtés est OMIS — jamais ``null`` contre ``null`` ;
* un champ présent d'UN seul côté est un écart réel, ``None`` du côté où il
  manque — jamais remplacé par ``0``.

Module PUR : aucune base, aucun réseau ; il lit des attributs
(``roof_layout``, ``layout_hash``, ``resultat``, ``version_moteur``).
"""
from __future__ import annotations

from types import SimpleNamespace

__all__ = [
    'CHAMPS_FIXES', 'LIBELLE_ETAT_COURANT', 'comparer_versions',
    'etat_courant', 'texte_des_ecarts',
]

#: Les grandeurs globales, dans l'ordre de publication.
CHAMPS_FIXES = (
    ('modules', 'Nombre de modules'),
    ('kwc', 'Puissance crête (kWc)'),
    ('pans', 'Nombre de pans'),
    ('obstacles', "Nombre d'obstacles"),
)

#: Les grandeurs de SUIVI, publiées après celles des pans.
CHAMPS_SUIVI = (
    ('layout_hash', 'Empreinte de la conception'),
    ('version_moteur', 'Version du moteur'),
)

#: Le libellé de l'état COURANT quand aucune version ``contre`` n'est donnée.
LIBELLE_ETAT_COURANT = 'État courant'


def _dict(valeur):
    return valeur if isinstance(valeur, dict) else {}


def _nombre(valeur):
    """Un NOMBRE au sens strict (ni booléen, ni texte illisible), ou None."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or abs(nombre) == float('inf'):
        return None
    return nombre


def _entier(valeur):
    nombre = _nombre(valeur)
    return int(nombre) if nombre is not None else None


def _zones(layout):
    zones = layout.get('zones')
    return [z for z in zones if isinstance(z, dict)] \
        if isinstance(zones, (list, tuple)) else []


def _modules(layout, zones):
    """``result.panels`` d'abord ; à défaut, les cellules POSÉES comptées."""
    total = _entier(_dict(layout.get('result')).get('panels'))
    if total is not None:
        return total
    listes = [_dict(zone.get('geometry')).get('panels') for zone in zones]
    listes = [liste for liste in listes if isinstance(liste, (list, tuple))]
    if not listes:
        return None
    return sum(1 for liste in listes for cellule in liste
               if isinstance(cellule, dict))


def _orientation(zone):
    geometrie = _dict(zone.get('geometry'))
    azimut = _nombre(geometrie.get('azimuthDeg')
                     if 'azimuthDeg' in geometrie
                     else zone.get('facingAzimuthDeg'))
    inclinaison = _nombre(geometrie.get('tiltDeg')
                          if 'tiltDeg' in geometrie
                          else zone.get('pitchDeg'))
    return azimut, inclinaison


def _version_moteur(etat):
    brute = getattr(etat, 'version_moteur', '') or ''
    if brute:
        return str(brute)
    resultat = _dict(getattr(etat, 'resultat', None))
    brute = (resultat.get('version_moteur')
             or _dict(resultat.get('simulation')).get('version_moteur'))
    return str(brute) if brute else None


def _grandeurs(etat):
    """``{champ: (libelle, valeur)}`` d'UN état, dans l'ordre de publication.

    Les pans sont indexés par leur ``id`` du document (repère stable d'une
    version à l'autre) ; un pan sans ``id`` prend ``PAN-<rang>`` comme la
    planche (``planche.py``).
    """
    layout = getattr(etat, 'roof_layout', None)
    grandeurs = {}
    if isinstance(layout, dict):
        zones = _zones(layout)
        grandeurs['modules'] = _modules(layout, zones)
        grandeurs['kwc'] = _nombre(_dict(layout.get('result')).get('kwc'))
        grandeurs['pans'] = len(zones)
        grandeurs['obstacles'] = sum(
            len([o for o in zone.get('obstacles') if isinstance(o, dict)])
            if isinstance(zone.get('obstacles'), (list, tuple)) else 0
            for zone in zones)
    else:
        zones = []
    valeurs = {cle: (libelle, grandeurs.get(cle))
               for cle, libelle in CHAMPS_FIXES}
    for rang, zone in enumerate(zones, start=1):
        repere = str(zone.get('id') or 'PAN-%d' % rang)
        nom = str(zone.get('label') or '') or repere
        azimut, inclinaison = _orientation(zone)
        valeurs['pan:%s:azimut_deg' % repere] = (
            'Orientation du pan « %s » (°)' % nom, azimut)
        valeurs['pan:%s:inclinaison_deg' % repere] = (
            'Inclinaison du pan « %s » (°)' % nom, inclinaison)
    valeurs['layout_hash'] = (CHAMPS_SUIVI[0][1],
                              getattr(etat, 'layout_hash', '') or None)
    valeurs['version_moteur'] = (CHAMPS_SUIVI[1][1], _version_moteur(etat))
    return valeurs


def _egales(avant, apres):
    if isinstance(avant, float) or isinstance(apres, float):
        if avant is None or apres is None:
            return False
        return round(float(avant), 6) == round(float(apres), 6)
    return avant == apres


def _ordre(gauche, droite):
    """Les champs fixes, puis les pans (gauche puis nouveaux), puis le suivi."""
    ordre = [cle for cle, _libelle in CHAMPS_FIXES]
    for cote in (gauche, droite):
        for cle in cote:
            if cle.startswith('pan:') and cle not in ordre:
                ordre.append(cle)
    return ordre + [cle for cle, _libelle in CHAMPS_SUIVI]


def _horodatage(moment):
    """Même écriture que l'historique (``views/calepinages.py::_horodatage``)."""
    return moment.isoformat() if moment is not None else None


def _descripteur(etat):
    pk = getattr(etat, 'pk', None)
    libelle = getattr(etat, 'libelle', '') or ''
    return {
        'id': pk,
        'libelle': libelle or ('Version #%s' % pk if pk is not None
                               else LIBELLE_ETAT_COURANT),
        'cree_le': _horodatage(getattr(etat, 'created_at', None)),
        'layout_hash': getattr(etat, 'layout_hash', '') or '',
    }


def etat_courant(calepinage):
    """L'état COURANT du calepinage, sous la forme d'une version sans ``id``.

    Sert de ``droite`` quand aucune version ``contre`` n'est demandée : « qu'est-
    ce qui a changé depuis cette version ? ». ``cree_le`` est la dernière
    modification du calepinage.
    """
    return SimpleNamespace(
        pk=None, libelle=LIBELLE_ETAT_COURANT,
        created_at=getattr(calepinage, 'updated_at', None),
        roof_layout=getattr(calepinage, 'roof_layout', None),
        layout_hash=getattr(calepinage, 'layout_hash', '') or '',
        resultat=getattr(calepinage, 'resultat', None),
        version_moteur=getattr(calepinage, 'version_moteur', '') or '')


def comparer_versions(gauche, droite):
    """``{gauche, droite, ecarts}`` — la forme du contrat CALX333.

    ``avant`` se lit à GAUCHE, ``apres`` à DROITE. LECTURE PURE.
    """
    valeurs_g = _grandeurs(gauche)
    valeurs_d = _grandeurs(droite)
    ecarts = []
    for cle in _ordre(valeurs_g, valeurs_d):
        libelle_g, avant = valeurs_g.get(cle, (None, None))
        libelle_d, apres = valeurs_d.get(cle, (None, None))
        if avant is None and apres is None:
            continue  # absent des DEUX côtés : omis, jamais null contre null
        if _egales(avant, apres):
            continue
        ecarts.append({'champ': cle, 'libelle': libelle_d or libelle_g,
                       'avant': avant, 'apres': apres})
    return {
        'gauche': _descripteur(gauche),
        'droite': _descripteur(droite),
        'ecarts': ecarts,
    }


def _texte_valeur(valeur):
    if valeur is None:
        return '—'
    if isinstance(valeur, str) and len(valeur) == 64:
        return valeur[:12]  # une empreinte se lit par son préfixe
    return str(valeur)


def texte_des_ecarts(ecarts):
    """Les écarts en UNE phrase française, pour le chatter (restauration)."""
    if not ecarts:
        return 'Aucun écart sur les grandeurs comparées.'
    return ' ; '.join('%s : %s → %s' % (ecart['libelle'],
                                        _texte_valeur(ecart['avant']),
                                        _texte_valeur(ecart['apres']))
                      for ecart in ecarts) + '.'
