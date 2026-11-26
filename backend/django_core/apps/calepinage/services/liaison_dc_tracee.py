"""Liaison DC tracée (suite ACAL1317) — UNE longueur de liaison DC, avec le tracé du plan.

LE DÉFAUT CORRIGÉ
-----------------
Deux longueurs de la même liaison DC coexistaient dans le calepinage :

* le TRACÉ du plan (``roof_layout.electrical.cheminements[]``), mesuré par
  ``services/troncons.py`` (CALX224) : c'est lui que la pastille « Câble côté
  panneaux » de l'étape Électrique, le métré du bordereau (CALX227) et les
  verdicts de chute par tronçon (CALX225/226) affichent ;
* les scalaires SAISIS de ``entree.cheminement`` (course jusqu'au point de
  collecte + descente + coffret → onduleur), lus par
  ``services/cables.py::longueur_dc`` : c'est sur eux que la perte ohmique DC
  de la SIMULATION et la vérification de chute du câble ``W1`` calculaient.

CE QUE LE TRACÉ REMPLACE — ET SEULEMENT ÇA
-------------------------------------------
Le tracé que l'atelier PROPOSE (``electrique3d.ts::pointsProposes``) part du
CENTRE du pan et porte des points ``[lng, lat]`` sans altitude : c'est le
passage HORIZONTAL sur le plan, rien de plus. Il ne remplace donc que la
partie horizontale ; la liaison DC d'un pan tracé vaut :

1. la course du module le PLUS ÉLOIGNÉ jusqu'au DÉPART du tracé — la même
   fonction que la règle d'avant (``cables.course_de_chaine``, motif de
   parcours CALX218 compris), le départ remplaçant le point de collecte ;
2. le passage horizontal : le tracé (somme des segments À PLAT de chaque
   tronçon, par le même projeteur que ``troncons.py``, plus la
   ``longueurSaisieM`` d'un tronçon), SAUF si ``coffret_vers_onduleur_m`` est
   saisi — la saisie l'emporte pour SA part ;
3. la partie verticale : ``descente_m`` SAISIE si elle l'est (la saisie
   l'emporte toujours), sinon la différence d'altitude des deux BOUTS du
   chemin quand tous deux portent ``altitudeM`` ; ni l'une ni l'autre ⇒ la
   liaison du pan reste INCONNUE, comme aujourd'hui, et le motif nomme la
   descente.

Un pan dont le point de collecte ET le coffret → onduleur sont saisis garde
la règle d'avant, octet pour octet : le tracé n'y apporte rien.

CE QU'IL IGNORE, COMME AUJOURD'HUI
-----------------------------------
Un tracé qui n'aboutit à aucun onduleur posé, un tracé « orphelin », un
tronçon sans longueur mesurable, un tronçon AC ou de terre : le pan garde la
règle d'avant. C'est ``services/cables.py`` qui décide QUAND le tracé sert
(``dc_m`` non saisi, calcul fait après ``regles_calcul.COUPURE_LIAISON_DC_TRACEE``).
Lecture pure, sans base et sans effet de bord.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from core.calepinage.geo import projeteur_local

from .cables import (
    MOTIF_PAN_SANS_TRACE, ORIGINE_MIXTE, ORIGINE_PLAN, ORIGINE_SAISIE, Longueur, course_de_chaine,
)
from .troncons import COTE_DC, _cheminements, _longueur_du_troncon, _longueur_polyligne, _point, _repere
from .valeurs import nombre as _nombre

__all__ = ['courses_tracees', 'liaison_du_pan', 'liaison_retenue', 'PREFIXE_DETAIL_TRACE']

TYPE_ONDULEUR = 'onduleur'

#: Les organes qu'un tracé DC TRAVERSE entre le pan et l'onduleur : le coffret
#: DC (et le parafoudre qui y est posé). Tout autre organe arrête le chemin.
TYPES_DE_PASSAGE = ('coffret_dc', 'parafoudre')

#: Le début du ``detail`` d'une liaison où le tracé est ENTRÉ : c'est lui qui
#: distingue, dans ``cables.py``, une liaison tracée d'une liaison saisie.
PREFIXE_DETAIL_TRACE = 'liaison relevée sur le tracé du plan'


@dataclass(frozen=True)
class CheminTrace:
    """Le chemin DC tracé d'UN pan jusqu'à un onduleur, mesuré à plat."""

    onduleur: str
    reperes: Tuple[str, ...]
    depart: Optional[Tuple[float, float]]
    horizontal_m: float
    denivele_m: Optional[float]
    origine: str


def _texte(valeur):
    return str(valeur).strip() if valeur is not None else ''


def _organes(document):
    """``(onduleurs, passages)`` — les ``id`` des organes POSÉS du document."""
    electrique = (document or {}).get('electrical')
    equipements = electrique.get('equipements') if isinstance(electrique, dict) else None
    onduleurs, passages = set(), set()
    for organe in equipements if isinstance(equipements, (list, tuple)) else ():
        if not isinstance(organe, dict) or not _texte(organe.get('id')):
            continue
        if organe.get('type') == TYPE_ONDULEUR:
            onduleurs.add(_texte(organe.get('id')))
        elif organe.get('type') in TYPES_DE_PASSAGE:
            passages.add(_texte(organe.get('id')))
    return onduleurs, passages


def _troncon_mesure(cheminement, rang):
    """``(repère, points, à plat (m), saisie (m), origine)`` d'un tronçon DC mesurable, ou ``None``.

    La validité est celle de ``troncons.py`` (même refus : ni tracé ni saisie,
    saisie négative) ; la longueur horizontale ignore les altitudes.
    """
    longueur, _motif = _longueur_du_troncon(cheminement, rang)
    if longueur is None:
        return None
    bruts = cheminement.get('points') if isinstance(cheminement.get('points'), (list, tuple)) else ()
    points = [point for point in (_point(brut) for brut in bruts) if point is not None]
    a_plat = _longueur_polyligne([(lng, lat, None) for lng, lat, _alt in points]) or 0.0
    saisie = _nombre(cheminement.get('longueurSaisieM')) or 0.0
    return (_repere(cheminement, rang), points, a_plat, saisie, longueur.origine)


def _graphe_dc(document):
    """``{de: [(vers, tronçon mesuré)]}`` des tronçons DC du document."""
    graphe = {}
    for rang, cheminement in enumerate(_cheminements(document), start=1):
        de, vers = _texte(cheminement.get('de')), _texte(cheminement.get('vers'))
        if cheminement.get('cote') != COTE_DC or not de or not vers:
            continue
        mesure = _troncon_mesure(cheminement, rang)
        if mesure is not None:
            graphe.setdefault(de, []).append((vers, mesure))
    return graphe


def _chemins(depart, graphe, onduleurs, passages, vus):
    """Les chemins ``((vers, tronçon mesuré), …)`` de ``depart`` à un onduleur."""
    for vers, mesure in graphe.get(depart, ()):
        if vers in vus:
            continue
        etape = ((vers, mesure),)
        if vers in onduleurs:
            yield etape
        elif vers in passages:
            for suite in _chemins(vers, graphe, onduleurs, passages, vus | {vers}):
                yield etape + suite


def _chemin_trace(etapes):
    premiers = etapes[0][1][1]
    derniers = etapes[-1][1][1]
    debut = premiers[0] if premiers else None
    fin = derniers[-1] if derniers else None
    denivele = (abs(fin[2] - debut[2]) if debut is not None and fin is not None
                and debut[2] is not None and fin[2] is not None else None)
    origines = {mesure[4] for _vers, mesure in etapes}
    return CheminTrace(
        onduleur=etapes[-1][0], reperes=tuple(mesure[0] for _vers, mesure in etapes),
        depart=(debut[0], debut[1]) if debut is not None else None,
        horizontal_m=sum(mesure[2] + mesure[3] for _vers, mesure in etapes),
        denivele_m=denivele, origine=ORIGINE_PLAN if origines == {ORIGINE_PLAN} else ORIGINE_MIXTE)


def courses_tracees(document):
    """``{clé de pan: CheminTrace}`` — le chemin DC tracé de chaque pan jusqu'à un onduleur.

    Un pan sans tracé qui aboutit à un onduleur posé n'a PAS d'entrée : il garde
    la règle des longueurs saisies. Plusieurs chemins : le plus long.
    """
    from .production import cle_de_pan

    onduleurs, passages = _organes(document)
    zones = (document or {}).get('zones') if isinstance(document, dict) else None
    if not onduleurs or not isinstance(zones, (list, tuple)):
        return {}
    graphe = _graphe_dc(document)
    courses = {}
    for rang, zone in enumerate(zones, start=1):
        if not isinstance(zone, dict):
            continue
        cle = cle_de_pan(zone, rang)
        chemins = [_chemin_trace(etapes)
                   for etapes in _chemins(cle, graphe, onduleurs, passages, frozenset({cle}))]
        if chemins:
            courses[cle] = max(chemins, key=lambda c: c.horizontal_m + (c.denivele_m or 0.0))
    return courses


def _depart_dans_le_pan(zone, chemin):
    """Le départ du tracé en ``{cx, cy}`` (mètres ENU de ``geometry.origin``), ou ``None``."""
    origine = (zone.get('geometry') or {}).get('origin')
    if chemin.depart is None or not isinstance(origine, (list, tuple)) or len(origine) < 2:
        return None
    lng0, lat0 = _nombre(origine[0]), _nombre(origine[1])
    if lng0 is None or lat0 is None:
        return None
    cx, cy = projeteur_local((lng0, lat0))(chemin.depart)
    return {'cx': cx, 'cy': cy}


def liaison_du_pan(zone, chemin, saisie_du_pan, descente, vers_onduleur):
    """``(Longueur | None, motif)`` — la liaison DC d'UN pan tracé (cf. le bandeau).

    Raises:
        MotifDeParcoursInvalide: motif de parcours saisi hors énumération.
    """
    depart = _depart_dans_le_pan(zone, chemin)
    if depart is None:
        return (None, "le départ du tracé « %s » ne se place pas dans le pan (point ou "
                      "« geometry.origin » absent) : la course depuis le module le plus "
                      "éloigné n'est pas mesurable" % chemin.reperes[0])
    course = course_de_chaine(None, (zone.get('geometry') or {}).get('panels'),
                              saisie_du_pan.get('motif_parcours'), point_collecte=depart)
    if course is None:
        return (None, "centres de modules absents du plan : la course DC de ce pan n'est "
                      "pas mesurable")
    if descente is None and chemin.denivele_m is None:
        return (None, "descente verticale non saisie (m), et le tracé ne porte pas "
                      "l'altitude de ses deux bouts — elle ne se lit sur aucun plan")
    reperes = ', '.join('« %s »' % repere for repere in chemin.reperes)
    composantes = (
        ('module le plus éloigné → départ du tracé %s' % reperes, course.valeur_m, ORIGINE_PLAN),
        (('coffret → onduleur', vers_onduleur, ORIGINE_SAISIE) if vers_onduleur is not None
         else ('tracé %s jusqu\'à l\'onduleur « %s », à plat' % (reperes, chemin.onduleur),
               chemin.horizontal_m, chemin.origine)),
        (('descente verticale', descente, ORIGINE_SAISIE) if descente is not None
         else ('dénivelé des deux bouts du tracé', chemin.denivele_m, ORIGINE_PLAN)),
    )
    saisies = {origine for _poste, _valeur, origine in composantes} - {ORIGINE_PLAN}
    return (Longueur(
        valeur_m=sum(valeur for _poste, valeur, _origine in composantes),
        origine=ORIGINE_MIXTE if saisies else ORIGINE_PLAN,
        detail="%s (pan « %s ») : %s" % (
            PREFIXE_DETAIL_TRACE, str(zone.get('label') or ''),
            ' + '.join('%s (%s)' % (poste, origine) for poste, _valeur, origine in composantes)),
        composantes=composantes), None)


def liaison_retenue(courses, manques, descente, vers_onduleur):
    """``(Longueur | None, manques)`` — la liaison DC la plus longue, un pan au moins tracé.

    ``courses`` : ``(libellé, valeur, Longueur)`` pour un pan tracé,
    ``(libellé, course, détail)`` pour un pan qui garde la règle d'avant (il lui
    faut alors la descente ET le coffret → onduleur saisis).
    """
    manques = list(manques)
    totaux = []
    for libelle, valeur, detail in courses:
        if isinstance(detail, Longueur):
            totaux.append(detail)
        elif descente is None or vers_onduleur is None:
            if MOTIF_PAN_SANS_TRACE not in manques:
                manques.append(MOTIF_PAN_SANS_TRACE)
        else:
            totaux.append(Longueur(
                valeur_m=valeur + descente + vers_onduleur, origine=ORIGINE_MIXTE,
                detail="course mesurée sur le plan (pan « %s » — %s) + descente et liaison "
                       "coffret → onduleur saisies" % (libelle, detail),
                composantes=(('course dans le pan « %s »' % libelle, valeur, ORIGINE_PLAN),
                             ('descente verticale', descente, ORIGINE_SAISIE),
                             ('coffret → onduleur', vers_onduleur, ORIGINE_SAISIE))))
    if manques or not totaux:
        return (None, tuple(manques))
    return (max(totaux, key=lambda longueur: longueur.valeur_m), ())
