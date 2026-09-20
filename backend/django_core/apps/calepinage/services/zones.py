"""CAL68 — porter les zones INTERDITE / RESERVEE / PREFEREE jusqu'au moteur.

LE CONSTAT
----------
Le moteur PUR traite déjà les quatre natures de contour
(``core/calepinage/types.py::NatureZone`` : ENVELOPPE / INTERDITE / RESERVEE /
PREFEREE ; retrait et aire retirée dans ``core/calepinage/zones.py``), et l'AO
les persiste (``apps/ao/models.py::ZoneAO``). Mais le document de l'atelier ne
connaissait que ``obstacles[]`` : une servitude ou une bande coupe-feu tracée
par le dessinateur ne changeait RIEN au compte publié — silencieusement.

CE QUE FAIT CE MODULE, ET CE QU'IL NE REFAIT PAS
------------------------------------------------
* il traduit ``roof_layout['exclusionZones']`` (schéma v2, CAL232) vers la
  forme de zone du CONTRAT MOTEUR. La forme n'est pas recopiée à la main :
  elle vient de ``core.calepinage.serialisation`` elle-même (voir ``_ZONE``
  plus bas), donc elle ne peut pas dériver du jour où le noyau ajoute un
  champ ;
* il NE DUPLIQUE PAS le traducteur AO (``apps/ao/calepinage_io.py::
  zones_vers_document``) : celui-là traduit des MODÈLES ``ZoneAO``, celui-ci
  un DOCUMENT JSON. Les deux convergent vers la même forme de contrat parce
  qu'ils la prennent au même endroit — le noyau ;
* il ne chiffre rien lui-même : l'aire retirée est celle de
  ``core.calepinage.zones.aire_retiree``, nature par nature.

NOMMAGE (décision CAL232, rappelée ici) : la tâche parle du « tableau
``zones[]`` », mais ce nom est PRIS depuis la v1 par les PANS de toiture.
Réutiliser ``zones`` casserait tout document existant et les trois
consommateurs backend d'un coup. Le tableau du document d'atelier s'appelle
donc ``exclusionZones`` ; côté MOTEUR, la clé reste ``zones`` (c'est le
contrat du noyau).

LE REPÈRE DES SOMMETS — CE QUE CE MODULE NE PEUT PAS DEVINER
-------------------------------------------------------------
Les sommets sont rendus DANS LE MÊME REPÈRE que ceux des pans du document.
Aucune projection n'est appliquée d'office : ce module ne sait pas, seul, si
le document est en degrés (lng/lat) ou déjà en mètres locaux, et PROJETER À
L'AVEUGLE produirait des aires fausses présentées comme justes. L'appelant
qui travaille en lng/lat passe donc ``projection=projeteur_local(origine)`` —
c'est le futur traducteur complet roof_layout → ``EntreeCalepinage`` (CAL78,
ABSENT du dépôt aujourd'hui) qui projettera pans ET zones ensemble.

ÉQUIVALENCE : un document SANS ``exclusionZones`` laisse l'entrée moteur
strictement inchangée — comportement d'aujourd'hui.
"""
from __future__ import annotations

import math

#: La clé du document d'atelier (v2) et celle du contrat MOTEUR.
CLE_LAYOUT = 'exclusionZones'
CLE_MOTEUR = 'zones'

__all__ = [
    'CLE_LAYOUT', 'CLE_MOTEUR', 'ZoneRefusee', 'natures_admises',
    'zones_moteur_depuis_layout', 'injecter_zones', 'chiffrage_zones',
    'projeteur_local',
]


class ZoneRefusee(ValueError):
    """Refus métier, en français, avec le CHAMP fautif nommé."""

    def __init__(self, message, champ=''):
        super().__init__(message)
        self.champ = champ


def natures_admises():
    """Les quatre natures du NOYAU — jamais une liste recopiée à la main."""
    from core.calepinage.types import NatureZone

    return tuple(nature.value for nature in NatureZone)


def projeteur_local(origine):
    """``(lon, lat) -> (x_m, y_m)`` autour de ``origine`` ``(lon, lat)``.

    Approximation locale plane, suffisante à l'échelle d'un toit, et
    IDENTIQUE à celle de CAL237 pour que les deux services ne fabriquent pas
    deux repères différents du même site.
    """
    lon0, lat0 = float(origine[0]), float(origine[1])
    echelle_x = 111320.0 * math.cos(math.radians(lat0))

    def projeter(point):
        return ((float(point[0]) - lon0) * echelle_x,
                (float(point[1]) - lat0) * 110540.0)

    return projeter


def _sommets(brute, champ, repere, projection):
    points = brute.get('vertices')
    if points is None:
        points = brute.get('sommets')
    if not isinstance(points, list):
        raise ZoneRefusee(
            f"La zone « {repere} » n'a pas de contour : « vertices » est "
            "attendu.", champ)
    propres = []
    for point in points:
        if (not isinstance(point, (list, tuple)) or len(point) < 2
                or any(isinstance(v, bool)
                       or not isinstance(v, (int, float))
                       for v in point[:2])):
            raise ZoneRefusee(
                f"Sommet illisible dans la zone « {repere} » "
                f"(reçu : {point!r}).", champ)
        propres.append(tuple(projection((point[0], point[1]))))
    if not propres:
        # Une zone en cours de saisie ne délimite rien : elle est IGNORÉE,
        # comme côté AO. L'appelant la verra simplement absente.
        return None
    if len(propres) < 3:
        raise ZoneRefusee(
            f"La zone « {repere} » n'a que {len(propres)} sommet(s) : un "
            "contour de moins de 3 points ne délimite aucune surface.", champ)
    return propres


def _nombre(valeur, champ, libelle, repere, *, defaut=None):
    if valeur is None:
        return defaut
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ZoneRefusee(
            f"« {libelle} » de la zone « {repere} » doit être un nombre "
            f"(reçu : {type(valeur).__name__}).", champ)
    if float(valeur) < 0:
        raise ZoneRefusee(
            f"« {libelle} » de la zone « {repere} » ne peut pas être négatif "
            f"(reçu : {valeur}).", champ)
    return float(valeur)


def zones_moteur_depuis_layout(roof_layout, *, projection=None):
    """Les zones du document d'atelier, en forme de contrat MOTEUR.

    Args:
        roof_layout: le document v2. ``exclusionZones`` absent ou vide ⇒
            ``[]`` (équivalence : comportement d'aujourd'hui).
        projection: ``(lon, lat) -> (x, y)``. Par défaut IDENTITÉ — voir
            l'en-tête : ce module ne projette jamais à l'aveugle.

    Raises:
        ZoneRefusee: nature inconnue, contour à 1-2 sommets, retrait négatif.
            Le champ nommé est ``exclusionZones[i]``.
    """
    from core.calepinage.serialisation import _zone
    from core.calepinage.types import NatureZone, Zone

    brutes = (roof_layout or {}).get(CLE_LAYOUT)
    if brutes is None:
        return []
    if not isinstance(brutes, list):
        raise ZoneRefusee(
            f"« {CLE_LAYOUT} » doit être une liste "
            f"(reçu : {type(brutes).__name__}).", CLE_LAYOUT)

    projection = projection or (lambda point: (float(point[0]),
                                               float(point[1])))
    sortie = []
    for rang, brute in enumerate(brutes):
        champ = f'{CLE_LAYOUT}[{rang}]'
        if not isinstance(brute, dict):
            raise ZoneRefusee(
                f"La zone n° {rang + 1} doit être un objet "
                f"(reçu : {type(brute).__name__}).", champ)
        repere = str(brute.get('id') or brute.get('repere')
                     or f'ZONE{rang + 1}')

        nature = brute.get('nature')
        try:
            nature = NatureZone(str(nature))
        except ValueError:
            raise ZoneRefusee(
                f"Nature de zone inconnue pour « {repere} » : "
                f"« {nature} ». Natures admises : "
                f"{', '.join(natures_admises())}.", champ)

        sommets = _sommets(brute, champ, repere, projection)
        if sommets is None:
            continue

        # La forme de sortie vient du NOYAU (`_zone`) : si le contrat moteur
        # gagne un champ, ce traducteur le suit sans être retouché.
        sortie.append(_zone(Zone(
            repere=repere,
            nature=nature,
            sommets=tuple(sommets),
            hauteur_m=_nombre(brute.get('heightM'), champ, 'Hauteur', repere),
            retrait_m=_nombre(brute.get('setbackM'), champ, 'Retrait', repere,
                              defaut=0.0),
        )))
    return sortie


def injecter_zones(document, roof_layout, *, projection=None):
    """Le document MOTEUR, enrichi des zones du document d'atelier.

    Le document d'origine n'est jamais modifié sur place. Un layout SANS
    ``exclusionZones`` rend le document tel quel (équivalence stricte) —
    y compris ses zones déjà présentes, qui ne sont donc jamais effacées par
    un document d'atelier muet.
    """
    zones = zones_moteur_depuis_layout(roof_layout, projection=projection)
    if not zones:
        return document
    enrichi = dict(document or {})
    enrichi[CLE_MOTEUR] = list(enrichi.get(CLE_MOTEUR) or []) + zones
    return enrichi


def chiffrage_zones(zones):
    """Ce que les zones COÛTENT, nature par nature (m²).

    * ``INTERDITE`` et ``RESERVEE`` RETIRENT de la surface posable — et la
      ``RESERVEE`` est chiffrée à part parce que c'est un argument de
      négociation (« voilà ce que votre réserve d'usage futur coûte ») ;
    * ``PREFEREE`` ne retire RIEN : c'est un bonus DOUX de départage entre
      plans déjà optimaux, qui ne change JAMAIS un compte. Son aire est
      publiée pour information, à zéro dans le retiré.

    Le calcul n'est pas refait ici : il vient de
    ``core.calepinage.zones.aire_retiree`` / ``aire_polygone``.
    """
    from core.calepinage.serialisation import _zone_depuis
    from core.calepinage.types import NatureZone
    from core.calepinage.zones import (
        NATURES_BLOQUANTES, aire_polygone, aire_retiree, sommets_decales,
    )

    objets = [_zone_depuis(z) for z in (zones or [])]
    par_nature = {}
    for nature in NatureZone:
        les_siennes = [z for z in objets if z.nature is nature]
        if nature in NATURES_BLOQUANTES:
            retiree = aire_retiree(les_siennes, nature=nature)
        else:
            # PREFEREE / ENVELOPPE ne retirent rien : le dire explicitement
            # vaut mieux que de laisser l'appelant additionner par erreur.
            retiree = 0.0
        par_nature[nature.value] = {
            'nombre': len(les_siennes),
            'aire_m2': sum(aire_polygone(sommets_decales(z.sommets,
                                                         z.retrait_m))
                           for z in les_siennes),
            'aire_retiree_m2': retiree,
        }
    return {
        'aire_retiree_m2': aire_retiree(objets),
        'par_nature': par_nature,
    }
