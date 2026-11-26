"""Liaison DC tracée (suite ACAL1317) — UNE longueur de liaison DC, celle du tracé.

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

L'écran montrait donc une longueur et calculait avec une autre (règle
fondateur du 23/11 : « un seul moteur, un seul chiffre par valeur, le plus
réaliste »).

CE QUE CE MODULE FAIT
---------------------
Il rend, PAN PAR PAN, la liaison DC MESURÉE sur le tracé, du pan jusqu'à un
onduleur posé : la même mesure que ``troncons.py`` (``_longueur_du_troncon``,
jamais une seconde formule), tronçon après tronçon quand le tracé passe par un
coffret DC (``z1 → coffret → onduleur``). Plusieurs chemins d'un même pan :
le plus long (le câble tient la pire liaison, comme ``longueur_dc``).

CE QU'IL IGNORE, COMME AUJOURD'HUI
-----------------------------------
Un tracé qui n'aboutit à aucun onduleur posé, un tracé « orphelin » (une
extrémité qui ne résout vers rien), un tronçon sans longueur mesurable, un
tronçon AC ou de terre : aucun ne fournit de liaison, et le pan garde la règle
d'avant.

C'est ``services/cables.py`` qui décide QUAND cette longueur sert (rien de
saisi, simulation calculée après ``regles_calcul.COUPURE_LIAISON_DC_TRACEE``)
— ce module ne fait que mesurer, sans base et sans effet de bord.
"""
from __future__ import annotations

from .cables import ORIGINE_MIXTE, ORIGINE_PLAN, ORIGINE_SAISIE, Longueur
from .troncons import COTE_DC, _cheminements, _longueur_du_troncon, _repere

__all__ = ['courses_tracees', 'liaison_la_plus_longue', 'PREFIXE_DETAIL_TRACE']

TYPE_ONDULEUR = 'onduleur'

#: Les organes qu'un tracé DC TRAVERSE entre le pan et l'onduleur : le coffret
#: DC (et le parafoudre qui y est posé). Tout autre organe arrête le chemin.
TYPES_DE_PASSAGE = ('coffret_dc', 'parafoudre')

#: Le début du ``detail`` d'une liaison tracée : c'est lui qui distingue, dans
#: ``cables.py``, une liaison tracée d'une liaison saisie (« course la plus
#: longue mesurée… »).
PREFIXE_DETAIL_TRACE = 'liaison la plus longue tracée sur le plan'


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


def _graphe_dc(document):
    """``{de: [(vers, repère, Longueur)]}`` des tronçons DC MESURÉS du document."""
    graphe = {}
    for rang, cheminement in enumerate(_cheminements(document), start=1):
        de, vers = _texte(cheminement.get('de')), _texte(cheminement.get('vers'))
        if cheminement.get('cote') != COTE_DC or not de or not vers:
            continue
        longueur, _motif = _longueur_du_troncon(cheminement, rang)
        if longueur is not None:
            graphe.setdefault(de, []).append((vers, _repere(cheminement, rang), longueur))
    return graphe


def _chemins(depart, graphe, onduleurs, passages, vus):
    """Les chemins ``((repère, de, vers, Longueur), …)`` de ``depart`` à un onduleur."""
    for vers, repere, longueur in graphe.get(depart, ()):
        if vers in vus:
            continue
        etape = ((repere, depart, vers, longueur),)
        if vers in onduleurs:
            yield etape
        elif vers in passages:
            for suite in _chemins(vers, graphe, onduleurs, passages, vus | {vers}):
                yield etape + suite


def _longueur_du_chemin(libelle, chemin):
    origines = {longueur.origine for _r, _de, _vers, longueur in chemin}
    origine = (ORIGINE_PLAN if origines == {ORIGINE_PLAN}
               else ORIGINE_SAISIE if origines == {ORIGINE_SAISIE} else ORIGINE_MIXTE)
    reperes = ', '.join('« %s »' % repere for repere, _de, _vers, _l in chemin)
    return Longueur(
        valeur_m=sum(longueur.valeur_m for _r, _de, _vers, longueur in chemin),
        origine=origine,
        detail="tracé du pan « %s » jusqu'à l'onduleur « %s » (%s)" % (libelle, chemin[-1][2], reperes),
        composantes=tuple(("tronçon « %s » (« %s » → « %s »)" % (repere, de, vers), longueur.valeur_m,
                           longueur.origine) for repere, de, vers, longueur in chemin))


def courses_tracees(document):
    """``{clé de pan: Longueur}`` — la liaison DC tracée de chaque pan jusqu'à un onduleur.

    Un pan sans tracé qui aboutit à un onduleur posé n'a PAS d'entrée : il garde
    la règle des longueurs saisies. Lecture pure du document.
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
        chemins = list(_chemins(cle, graphe, onduleurs, passages, frozenset({cle})))
        if chemins:
            pire = max(chemins, key=lambda c: sum(e[3].valeur_m for e in c))
            courses[cle] = _longueur_du_chemin(str(zone.get('label') or cle), pire)
    return courses


def liaison_la_plus_longue(course):
    """La liaison DC retenue quand TOUS les pans posés sont tracés : la plus longue."""
    return Longueur(
        valeur_m=course.valeur_m, origine=course.origine,
        detail="%s (%s) : aucune longueur saisie, la simulation et la chute de tension "
               "comptent ce tracé" % (PREFIXE_DETAIL_TRACE, course.detail),
        composantes=course.composantes)
