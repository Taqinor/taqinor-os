"""CALX224 — la longueur RÉELLE de chaque tronçon de câble.

LE DÉFAUT CORRIGÉ
-----------------
La seule longueur mesurée aujourd'hui est une distance à VOL D'OISEAU du
module le plus éloigné vers un point de collecte saisi
(``services/cables.py``), et la descente comme la liaison vers le TGBT sont
des scalaires « qui ne se lisent sur aucun plan ». Un tronçon coudé de 40 m
est donc compté comme sa corde, et l'installateur commande trop court.

CE QUE CE SERVICE FAIT
----------------------
Il lit les CHEMINEMENTS du document (``electrical.cheminements[]``, clé
racine optionnelle posée par CALX202) et, pour chaque entrée :

* somme les distances entre points consécutifs de la polyligne, dénivelé
  compris quand les DEUX extrémités d'un segment portent leur ``altitudeM`` ;
* ajoute la ``longueurSaisieM`` quand il y en a une (la traversée, la
  descente ou le passage que le plan ne porte pas) ;
* publie ``longueur_m`` ET ``longueur_origine`` (``plan`` / ``saisie`` /
  ``mixte``) — jamais un nombre nu.

C'est la discipline ``Longueur`` de ``services/cables.py`` ÉTENDUE au tracé :
la dataclasse y est importée telle quelle, avec ses composantes et leurs
origines, plutôt que redéfinie ici.

CE QU'IL NE FAIT JAMAIS
-----------------------
Aucune longueur par défaut n'est substituée. Un cheminement sans tracé
exploitable ET sans longueur saisie rend ``longueur_m: null`` (jamais ``0``,
qui se lirait « mesuré, et nul ») avec une entrée dans ``omissions[]`` qui
NOMME le tronçon, le champ et le motif en français — règle fondateur « zéro
chiffre inventé » (D-CALX 7).

FORME PUBLIÉE
-------------
``contract_samples/calepinage_troncons.json`` (CALX203) : ``troncons[]``,
``totaux``, ``omissions[]``. Les grandeurs de dimensionnement (section,
chute) arrivent avec CALX225/CALX226 ; ce module ne publie pour l'instant
que ce qu'il MESURE.
"""
from __future__ import annotations

import math

from .cables import ORIGINE_PLAN, ORIGINE_SAISIE, Longueur
from .zones import projeteur_local

__all__ = [
    'ORIGINE_MIXTE', 'COTE_DC', 'COTE_AC', 'COTE_TERRE',
    'troncons_du_calepinage',
]

#: Le vocabulaire d'origine PUBLIÉ est celui du DOCUMENT (CALX202,
#: ``electrical.cheminements[].origine`` : ``plan`` | ``saisie`` | ``mixte``),
#: repris tel quel par le contrat CALX203 (``longueur_origine``).
#: ``services/cables.py`` publie sa propre prose (« plan et saisie ») pour ses
#: deux liaisons forfaitaires : ses deux premiers termes sont IMPORTÉS
#: ci-dessus, seul le troisième diffère et c'est le document qui fait foi ici.
ORIGINE_MIXTE = 'mixte'

COTE_DC = 'dc'
COTE_AC = 'ac'
COTE_TERRE = 'terre'

#: Le chemin JSON de la clé racine lue — il sert à NOMMER le champ absent
#: dans les omissions, jamais à deviner quoi que ce soit.
CHAMP_CHEMINEMENTS = 'electrical.cheminements'


def _nombre(valeur):
    """``float`` ou ``None`` — un booléen n'est jamais une mesure."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _point(brut):
    """``(lng, lat, altitude_m | None)`` d'un point du document, ou ``None``.

    Une altitude absente vaut ``None``, jamais ``0`` : « altitudeM absente ne
    veut pas dire au sol » (CALX202).
    """
    if not isinstance(brut, dict):
        return None
    lng = _nombre(brut.get('lng'))
    lat = _nombre(brut.get('lat'))
    if lng is None or lat is None:
        return None
    return (lng, lat, _nombre(brut.get('altitudeM')))


def _points_du_cheminement(cheminement):
    """Les points EXPLOITABLES du tracé, dans l'ordre du document."""
    bruts = (cheminement or {}).get('points')
    if not isinstance(bruts, (list, tuple)):
        return []
    retenus = []
    for brut in bruts:
        point = _point(brut)
        if point is not None:
            retenus.append(point)
    return retenus


def _longueur_polyligne(points):
    """Somme des distances entre points consécutifs (m), ou ``None``.

    Le repère plan est celui de ``services/zones.py::projeteur_local``, le
    seul projeteur local du module : deux services qui fabriqueraient deux
    repères du même site mesureraient deux longueurs du même câble.

    Le dénivelé n'entre QUE lorsque les DEUX extrémités d'un segment portent
    leur ``altitudeM`` ; sinon le segment est compté à plat et aucun dénivelé
    n'est deviné.
    """
    if len(points) < 2:
        return None
    projeter = projeteur_local((points[0][0], points[0][1]))
    total = 0.0
    for amont, aval in zip(points, points[1:]):
        x_amont, y_amont = projeter((amont[0], amont[1]))
        x_aval, y_aval = projeter((aval[0], aval[1]))
        a_plat = math.hypot(x_aval - x_amont, y_aval - y_amont)
        if amont[2] is None or aval[2] is None:
            total += a_plat
        else:
            total += math.hypot(a_plat, aval[2] - amont[2])
    return total


def _repere(cheminement, rang):
    """Le nom du tronçon tel qu'un poseur le lit : son ``id``, sinon son rang."""
    identifiant = (cheminement or {}).get('id')
    texte = str(identifiant).strip() if identifiant is not None else ''
    return texte or ('cheminement n° %d' % rang)


def _longueur_du_troncon(cheminement, rang=1):
    """``(Longueur | None, motif | None)`` — la longueur d'UN cheminement.

    Trois cas, exactement ceux de l'exemple committé de CALX202 : polyligne
    seule (``plan``), longueur saisie seule (``saisie``), et les deux
    (``mixte`` — un tracé plus une descente que le plan ne porte pas).
    """
    cheminement = cheminement or {}
    nom = _repere(cheminement, rang)
    tracee = _longueur_polyligne(_points_du_cheminement(cheminement))
    saisie = _nombre(cheminement.get('longueurSaisieM'))

    if saisie is not None and saisie < 0:
        return (None,
                "le tronçon « %s » porte une longueur saisie négative "
                "(« longueurSaisieM » = %s) : une longueur de câble ne peut "
                "pas être négative — corrigez la saisie, elle n'est pas "
                "réinterprétée." % (nom, saisie))

    composantes = []
    if tracee is not None:
        composantes.append(('tracé relevé sur le plan', tracee, ORIGINE_PLAN))
    if saisie is not None:
        composantes.append(('longueur saisie', saisie, ORIGINE_SAISIE))

    if not composantes:
        return (None,
                "le tronçon « %s » n'a ni tracé exploitable (« points », deux "
                "points minimum) ni longueur saisie (« longueurSaisieM ») : "
                "tracez-le dans l'atelier, ou saisissez sa longueur en "
                "mètres — elle ne peut pas être devinée, et aucune longueur "
                "par défaut n'est substituée." % nom)

    if tracee is not None and saisie is not None:
        origine = ORIGINE_MIXTE
        detail = ("tracé relevé sur le plan (%.2f m) plus une longueur saisie "
                  "(%.2f m)" % (tracee, saisie))
    elif tracee is not None:
        origine = ORIGINE_PLAN
        detail = 'tracé relevé sur le plan, point à point'
    else:
        origine = ORIGINE_SAISIE
        detail = "longueur saisie : ce passage n'est pas tracé sur le plan"

    return (Longueur(
        valeur_m=sum(valeur for _poste, valeur, _origine in composantes),
        origine=origine, detail=detail,
        composantes=tuple(composantes)), None)


def _troncon_publie(cheminement, longueur, rang):
    """Les champs du tronçon que la MESURE seule permet de remplir."""
    return {
        'id': _repere(cheminement, rang),
        'cote': (cheminement or {}).get('cote'),
        'de': (cheminement or {}).get('de'),
        'vers': (cheminement or {}).get('vers'),
        'longueur_m': (None if longueur is None
                       else round(longueur.valeur_m, 2)),
        'longueur_origine': None if longueur is None else longueur.origine,
    }


def _omission(troncon, champ, motif):
    """Une omission NOMMÉE : le tronçon, le champ, et pourquoi en français."""
    return {'troncon': troncon, 'champ': champ, 'motif': motif}


def _cheminements(document):
    """``electrical.cheminements[]`` du document, ou une liste vide."""
    electrique = (document or {}).get('electrical')
    if not isinstance(electrique, dict):
        return []
    cheminements = electrique.get('cheminements')
    if not isinstance(cheminements, (list, tuple)):
        return []
    return [c for c in cheminements if isinstance(c, dict)]


def _omission_aucun_cheminement():
    """L'état vide : PAS de chute nulle, PAS de chute calculable."""
    return _omission(
        None, CHAMP_CHEMINEMENTS,
        "aucun cheminement n'est tracé sur ce plan : il n'y a pas de tronçon "
        "à mesurer. Tracez les liaisons dans l'atelier, ou saisissez leurs "
        "longueurs — un calepinage sans tracé n'a pas 0 % de chute, il n'a "
        "PAS de chute calculable.")


def _mesurer(document):
    """``{troncons, totaux, omissions}`` — la MESURE seule (CALX224)."""
    cheminements = _cheminements(document)
    if not cheminements:
        return {'troncons': [],
                'totaux': {'metre_par_section': []},
                'omissions': [_omission_aucun_cheminement()]}

    troncons = []
    omissions = []
    for rang, cheminement in enumerate(cheminements, start=1):
        longueur, motif = _longueur_du_troncon(cheminement, rang)
        publie = _troncon_publie(cheminement, longueur, rang)
        troncons.append(publie)
        if motif:
            omissions.append(_omission(publie['id'], 'longueur_m', motif))
    return {'troncons': troncons, 'totaux': {'metre_par_section': []},
            'omissions': omissions}


def troncons_du_calepinage(calepinage):
    """CALX224 — le métré tronçon par tronçon de CE calepinage.

    Enveloppe MINCE : elle ne fait que lire le document enregistré
    (``Calepinage.roof_layout``) et passer la main au noyau de calcul, qui
    travaille sur ``layout['electrical']`` seul. Aucune écriture, aucun
    effet de bord.
    """
    return _mesurer(getattr(calepinage, 'roof_layout', None))
