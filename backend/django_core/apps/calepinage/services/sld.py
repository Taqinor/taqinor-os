# -*- coding: utf-8 -*-
"""CALX233 — LE SCHÉMA UNIFILAIRE ÉDITABLE : libellés et repères persistés.

LE CONSTAT
----------
``core/electrique/schema.py`` compose chaque bloc DEPUIS LE CALCUL
(``blocs_du_schema``) : le titre d'un organe est un littéral du noyau
(« Sectionneur DC », « Différentiel type A »), son repère vient de la
protection retenue. ``views/schema.py`` ne fait que rendre le SVG. Un
dessinateur qui veut renommer UN organe — parce que le bureau de contrôle
attend « Interrupteur-sectionneur DC » ou parce que le repère du dossier est
« Q2 » — n'avait aucune porte. Parité : OpenSolar ajuste formes, libellés et
connexions de son SLD ; Aurora publie un éditeur d'étiquettes de conducteurs
et de composants.

OÙ VIT LA PERSISTANCE
---------------------
Sur le calepinage, dans le champ JSON qui porte DÉJÀ tout ce que le moteur
dépose (``Calepinage.resultat``), sous la clé ``sld_edition``. Aucune
migration : ``resultat`` est un ``JSONField`` existant, écrit de la même
façon que ``entree_electrique`` ou ``verdict_electrique``
(``services/electrique.py``), avec ``update_fields=['resultat',
'updated_at']`` pour qu'une édition de schéma ne réécrive jamais une
conception.

CE QUE L'ÉDITION NE PEUT PAS FAIRE
-----------------------------------
* **Créer un organe.** Un bloc n'est dessiné que parce que la conception l'a
  retenu. Une clef absente du dessin est REFUSÉE, et le refus la NOMME
  (règle fondateur « erreur → champ fautif »).
* **Changer un calibre, une section, une quantité.** Les textes édités
  écrasent le TITRE et le REPÈRE d'un bloc au rendu — rien d'autre. Le
  tableau d'équipements est construit par ``lignes_tableau`` depuis
  ``protections[]``/``cables[]`` : il ne passe par aucun texte édité, et un
  test l'arme en le comparant avant/après édition.
* **Publier un montant.** Un schéma est une pièce technique (D-CALX 5) :
  les mots d'argent sont refusés dans un libellé comme dans un repère, avec
  la même liste que la garde du contrat (``tests/test_calx204_contrat_sld
  .py::HORS_SUJET``).

LE DESSIN RESTE UNIQUE
----------------------
Le SVG n'est pas reconstruit ici : il est rendu par ``rendre_schema`` (le
moteur PUR), puis les seuls groupes ``<g data-bloc="…">`` dont le texte a
changé sont RÉÉMIS par l'émetteur du noyau lui-même (``_bloc_svg``) à la
place qu'il leur a donnée. Aucune seconde géométrie, aucun filtre de texte
sur le SVG rendu. Le jour où le noyau acceptera ses blocs en paramètre
(crochet attendu : ``core/electrique/schema.py::rendre_schema(..., blocs=)``),
cette recomposition disparaîtra sans rien changer au résultat.
"""
from __future__ import annotations

import re

__all__ = [
    'CLE_EDITION', 'RUBRIQUES', 'LONGUEUR_TEXTE_MAX', 'MOTS_D_ARGENT',
    'SldRefuse', 'edition_sld', 'enregistrer_edition_sld', 'rendu_du_schema',
]

#: La clé du bloc d'édition dans ``Calepinage.resultat`` (JSONField existant).
CLE_EDITION = 'sld_edition'

#: Les trois rubriques d'une édition, telles que le contrat CALX204 les fige
#: (``contract_samples/calepinage_sld.json``). Aucune autre n'est acceptée :
#: une rubrique inconnue est un corps qu'on n'a pas compris, pas une
#: tolérance.
RUBRIQUES = ('libelles', 'reperes', 'positions')

#: Longueur maximale d'un libellé ou d'un repère saisi. Convention de SAISIE,
#: aucun texte ne la fixe : le noyau tronque un titre à 22 caractères
#: (``core/electrique/schema.py::_CARACTERES_TITRE``), donc au-delà de cette
#: borne le dessinateur ne saisirait plus qu'une ellipse — la borne dit
#: « ce texte ne sera pas lu » au lieu de l'accepter en silence.
LONGUEUR_TEXTE_MAX = 120

#: Les mots d'argent refusés dans un texte édité — la MÊME liste que la garde
#: du contrat (``tests/test_calx204_contrat_sld.py::HORS_SUJET``), source
#: unique de cette règle. Un schéma part au bureau de contrôle et au
#: gestionnaire de réseau : aucun montant n'y a sa place (D-CALX 5).
MOTS_D_ARGENT = ('prix', 'marge', 'montant', 'mad', 'tva', 'remise')

_MOT_D_ARGENT_RE = re.compile(
    r'\b(?:%s)\b' % '|'.join(MOTS_D_ARGENT), re.IGNORECASE)


class SldRefuse(ValueError):
    """Une édition de schéma refusée, avec un message FRANÇAIS.

    ``champ`` porte le chemin de la saisie fautive tel que le contrat le
    décrit (``edition.positions.coffret_ac``) : l'écran pointe LE champ, il
    n'affiche pas un « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


# ─────────────────────────────────────────────── lecture de l'édition posée
def _edition_vide():
    return {'libelles': {}, 'reperes': {}, 'positions': {}}


def _point_lisible(brut):
    """``{x, y}`` numériques, ou ``None`` si la valeur n'en est pas un."""
    if not isinstance(brut, dict) or set(brut) != {'x', 'y'}:
        return None
    try:
        return {'x': float(brut['x']), 'y': float(brut['y'])}
    except (TypeError, ValueError):
        return None


def edition_sld(calepinage):
    """L'édition PERSISTÉE de ce calepinage, normalisée — jamais une erreur.

    Lecture TOLÉRANTE : ce qui est stocké a été écrit par
    ``enregistrer_edition_sld``, mais un document ancien ou tronqué ne doit
    pas faire tomber un GET. Toute entrée illisible est simplement ignorée ;
    le refus, lui, est le travail de l'écriture.
    """
    stocke = getattr(calepinage, 'resultat', None)
    stocke = stocke.get(CLE_EDITION) if isinstance(stocke, dict) else None
    edition = _edition_vide()
    if not isinstance(stocke, dict):
        return edition
    for rubrique in ('libelles', 'reperes'):
        valeurs = stocke.get(rubrique)
        if not isinstance(valeurs, dict):
            continue
        for clef, texte in valeurs.items():
            if isinstance(clef, str) and isinstance(texte, str) and texte:
                edition[rubrique][clef] = texte
    positions = stocke.get('positions')
    if isinstance(positions, dict):
        for clef, brut in positions.items():
            point = _point_lisible(brut)
            if isinstance(clef, str) and point is not None:
                edition['positions'][clef] = point
    return edition


# ────────────────────────────────────────────── validation d'une saisie
def _texte_valide(valeur, *, champ):
    if not isinstance(valeur, str):
        raise SldRefuse(
            "Le texte de « %s » doit être une chaîne de caractères : "
            "un schéma ne porte que des désignations et des repères."
            % champ.rsplit('.', 1)[-1], champ=champ)
    texte = ' '.join(valeur.split())
    if not texte:
        raise SldRefuse(
            "Le texte de « %s » est vide : retirez la clef de l'édition "
            "plutôt que d'effacer la désignation que le calcul a produite."
            % champ.rsplit('.', 1)[-1], champ=champ)
    if len(texte) > LONGUEUR_TEXTE_MAX:
        raise SldRefuse(
            "Le texte de « %s » dépasse %d caractères : la boîte du schéma "
            "n'en montre que les premiers, le reste ne serait jamais lu."
            % (champ.rsplit('.', 1)[-1], LONGUEUR_TEXTE_MAX), champ=champ)
    mot = _MOT_D_ARGENT_RE.search(texte)
    if mot is not None:
        raise SldRefuse(
            "Le texte de « %s » contient le mot « %s » : le schéma "
            "unifilaire est une pièce technique, aucun montant n'y a sa "
            "place." % (champ.rsplit('.', 1)[-1], mot.group(0)), champ=champ)
    return texte


def _clef_dessinee(clef, clefs, *, champ):
    if not isinstance(clef, str) or not clef:
        raise SldRefuse(
            "Une clef d'édition doit être le nom d'un bloc dessiné : "
            "« %s » n'en est pas un." % (clef,), champ=champ)
    if clef not in clefs:
        raise SldRefuse(
            "Le bloc « %s » n'est pas dessiné sur ce schéma : l'édition ne "
            "peut renommer ou déplacer qu'un organe retenu par la "
            "conception. Retirez-le de l'édition, ou désignez l'organe "
            "correspondant sur le calepinage." % clef, champ=champ)


def _rubrique_dict(corps, rubrique):
    valeurs = corps.get(rubrique)
    if valeurs is None:
        return {}
    if not isinstance(valeurs, dict):
        raise SldRefuse(
            "« %s » doit être un objet { clef du bloc : valeur }." % rubrique,
            champ='edition.%s' % rubrique)
    return valeurs


def _valider_edition(corps, dessin):
    """La saisie, validée contre LE dessin — aucune clef inventée.

    ``dessin`` est ce que ``rendu_du_schema`` a produit : ses ``blocs`` sont
    les organes réellement retenus, ses bornes sont celles de la planche.
    """
    if corps is None:
        corps = {}
    if not isinstance(corps, dict):
        raise SldRefuse(
            "Le corps attendu est un objet { libelles, reperes, positions }.",
            champ='edition')
    # Une enveloppe ``{"edition": {...}}`` est acceptée telle quelle : c'est
    # la forme que le contrat CALX204 publie en réponse, donc celle qu'un
    # écran renvoie naturellement.
    if set(corps) == {'edition'} and isinstance(corps['edition'], dict):
        corps = corps['edition']
    inconnues = sorted(set(corps) - set(RUBRIQUES))
    if inconnues:
        raise SldRefuse(
            "Rubrique inconnue « %s » : une édition de schéma ne porte que "
            "%s." % (inconnues[0], ', '.join(RUBRIQUES)),
            champ='edition.%s' % inconnues[0])

    clefs = {bloc['clef'] for bloc in dessin.get('blocs') or ()}
    edition = _edition_vide()
    for rubrique in ('libelles', 'reperes'):
        for clef, valeur in _rubrique_dict(corps, rubrique).items():
            champ = 'edition.%s.%s' % (rubrique, clef)
            _clef_dessinee(clef, clefs, champ=champ)
            edition[rubrique][clef] = _texte_valide(valeur, champ=champ)
    for clef, brut in _rubrique_dict(corps, 'positions').items():
        champ = 'edition.positions.%s' % clef
        _clef_dessinee(clef, clefs, champ=champ)
        edition['positions'][clef] = _position_valide(brut, dessin,
                                                      champ=champ)
    return edition


def _position_valide(brut, dessin, *, champ):
    """CALX234 y ajoutera les bornes de la planche ; ici, la FORME seulement."""
    point = _point_lisible(brut)
    if point is None:
        raise SldRefuse(
            "La position de « %s » doit être un objet { x, y } en points de "
            "planche." % champ.rsplit('.', 1)[-1], champ=champ)
    return point


# ────────────────────────────────────────────────────────── écriture
def enregistrer_edition_sld(calepinage, corps, *, dessin=None):
    """Valide puis PERSISTE l'édition du schéma de ce calepinage.

    ``dessin`` court-circuite le calcul de la conception : il est réservé aux
    APPELS INTERNES et aux tests, exactement comme ``materiel=`` sur
    ``services/electrique.py::conception_du_calepinage`` — aucune vue ne
    l'expose, pour qu'un corps de requête ne puisse jamais déclarer lui-même
    quels blocs sont dessinés.

    Raises:
        SldRefuse: clef inconnue, texte vide/trop long, mot d'argent, forme
            de position illisible — le refus NOMME toujours le champ.
    """
    if dessin is None:
        dessin = _dessin_du_calepinage(calepinage)
    edition = _valider_edition(corps, dessin)
    resultat = getattr(calepinage, 'resultat', None)
    resultat = dict(resultat) if isinstance(resultat, dict) else {}
    resultat[CLE_EDITION] = edition
    calepinage.resultat = resultat
    if getattr(calepinage, 'pk', None):
        calepinage.save(update_fields=['resultat', 'updated_at'])
    return edition


def _dessin_du_calepinage(calepinage):
    """Le dessin d'AUJOURD'HUI — la seule autorité sur « quels blocs ? ».

    Une conception incomplète ou bloquée ne dessine rien : l'édition n'a
    alors aucun organe à nommer, et toute clef sera refusée en la nommant.
    """
    from .electrique import bloquants_nommes, conception_du_calepinage

    conception, _materiel, _donnees, _document = conception_du_calepinage(
        calepinage)
    if (list(getattr(conception, 'manquantes', ()) or ())
            or list(bloquants_nommes(conception) or ())):
        return {'svg': None, 'blocs': (), 'liaisons': ()}
    return rendu_du_schema(getattr(conception, 'entree', None),
                           getattr(conception, 'resultat', None),
                           edition=edition_sld(calepinage))


# ──────────────────────────────────────────────── le dessin, édition comprise
def _places(blocs, positions):
    """Les places des blocs, PAR LE MOTEUR — jamais une seconde géométrie.

    Les trois lignes que ``rendre_schema`` exécute pour se placer sont
    appelées ici sur les mêmes entrées : le format de planche dépend du
    nombre d'organes EN SÉRIE (la branche batterie pend sous son porteur et
    n'occupe aucune rangée), puis le serpentin place tout le monde.

    Crochet attendu hors de ce fichier (cf. rapport de lane) :
    ``core/electrique/schema.py`` n'expose pas encore de
    ``places_du_schema(entree, resultat, positions=…)`` publique — d'ici là,
    ce sont ses propres fonctions qui sont appelées, pas une copie.
    """
    from core.electrique.schema import (
        _EN_BRANCHE, _format_planche, _positions,
    )

    en_serie = sum(1 for bloc in blocs if bloc.clef not in _EN_BRANCHE)
    largeur, hauteur = _format_planche(en_serie)
    return _positions(blocs, largeur, positions or None), largeur, hauteur


def _blocs_edites(blocs, edition):
    """Les blocs du calcul, dont le TITRE et le REPÈRE seuls peuvent changer.

    Le bloc inchangé est rendu TEL QUEL (même objet) : c'est ce qui permet au
    rendu de ne réémettre que ce qui a bougé.
    """
    from core.electrique.schema import Bloc

    sortie = []
    for bloc in blocs:
        titre = edition['libelles'].get(bloc.clef, bloc.titre)
        repere = edition['reperes'].get(bloc.clef, bloc.repere)
        if titre == bloc.titre and repere == bloc.repere:
            sortie.append(bloc)
        else:
            sortie.append(Bloc(bloc.clef, titre, bloc.sous_titre, repere))
    return tuple(sortie)


def _svg_avec_blocs_edites(svg, places, origine):
    """Réémet, À SA PLACE, chaque groupe de bloc dont le texte a changé.

    ``data-bloc`` est un CONTRAT de lecture déclaré par le noyau
    (``core/electrique/schema.py::_bloc_svg``) : c'est par lui que le groupe
    est retrouvé, et c'est l'émetteur du noyau qui le réécrit. Le reste du
    SVG — liaisons, amorces MPPT, barrette de terre, tableau, cartouche —
    n'est pas touché : un libellé édité ne déplace rien et ne renomme rien
    d'autre.
    """
    from html import escape

    from core.electrique.schema import _bloc_svg

    for bloc, x, y, _rangee, _branche in places:
        if bloc is origine.get(bloc.clef):
            continue
        marque = '<g data-bloc="%s"' % escape(bloc.clef, quote=True)
        debut = svg.find(marque)
        if debut < 0:
            continue
        fin = svg.find('</g>', debut)
        if fin < 0:
            continue
        svg = svg[:debut] + _bloc_svg(x, y, bloc) + svg[fin + len('</g>'):]
    return svg


def _blocs_publies(places, edition):
    """Les sept champs par bloc du contrat CALX204, dans l'ordre du dessin.

    ``verrouille`` dit que la position vient de l'ÉDITION : le serpentin ne
    la recalculera plus. ``x``/``y`` sont arrondis au dixième, comme les
    coordonnées que le SVG écrit (``core/electrique/schema.py::_n``).
    """
    forcees = edition['positions']
    return tuple({
        'clef': bloc.clef,
        'repere': bloc.repere,
        'titre': bloc.titre,
        'sous_titre': bloc.sous_titre,
        'x': round(float(x), 1),
        'y': round(float(y), 1),
        'verrouille': bloc.clef in forcees,
    } for bloc, x, y, _rangee, _branche in places)


def _liaisons(places):
    """Une liaison par lien DESSINÉ : la chaîne série, puis les branches.

    Les deux points sont ceux où le SVG accroche sa liaison (bord à bord dans
    une rangée, ventre à sommet d'une rangée à l'autre, ventre du porteur au
    sommet de la branche). Le coude du SVG est une commodité de lecture, pas
    une information électrique : un consommateur de ces liaisons (l'export
    DXF, CALX235) relie les deux points.
    """
    from core.electrique.schema import _BLOC_H, _BLOC_L

    serie = [place for place in places if not place[4]]
    liaisons = []
    for depart, arrivee in zip(serie, serie[1:]):
        bloc_a, xa, ya, rangee_a, _ = depart
        bloc_b, xb, yb, rangee_b, _ = arrivee
        if rangee_a == rangee_b:
            if xb >= xa:
                points = ((xa + _BLOC_L, ya + _BLOC_H / 2),
                          (xb, yb + _BLOC_H / 2))
            else:
                points = ((xa, ya + _BLOC_H / 2),
                          (xb + _BLOC_L, yb + _BLOC_H / 2))
        else:
            points = ((xa + _BLOC_L / 2, ya + _BLOC_H),
                      (xb + _BLOC_L / 2, yb))
        liaisons.append({'depart': bloc_a.clef, 'arrivee': bloc_b.clef,
                         'nature': 'serie', 'points': points})
    ancre = next((place for place in serie if place[0].clef == 'onduleur'),
                 None)
    if ancre is not None:
        for place in places:
            if not place[4]:
                continue
            liaisons.append({
                'depart': ancre[0].clef, 'arrivee': place[0].clef,
                'nature': 'branche',
                'points': ((ancre[1] + _BLOC_L / 2, ancre[2] + _BLOC_H),
                           (place[1] + _BLOC_L / 2, place[2]))})
    return tuple(liaisons)


def rendu_du_schema(entree, resultat, *, edition=None, cartouche=None):
    """Le dessin d'une conception, ÉDITION APPLIQUÉE — SVG et blocs d'accord.

    Returns:
        ``{svg, blocs, liaisons, largeur, hauteur}``. ``blocs`` porte les
        sept champs du contrat CALX204 et EST le dessin : ce que ``edition``
        demande y est déjà appliqué, jamais publié à côté.
    """
    from core.electrique.schema import blocs_du_schema, rendre_schema

    # L'édition reçue n'est JAMAIS modifiée ici : on en prend une copie
    # normalisée (les trois rubriques toujours présentes), pour qu'un appelant
    # ne récupère pas un dictionnaire enrichi à son insu.
    recue = edition if isinstance(edition, dict) else {}
    edition = _edition_vide()
    for rubrique in RUBRIQUES:
        valeurs = recue.get(rubrique)
        if isinstance(valeurs, dict):
            edition[rubrique] = dict(valeurs)
    origine = blocs_du_schema(entree, resultat)
    blocs = _blocs_edites(origine, edition)
    places, largeur, hauteur = _places(blocs, None)
    svg = rendre_schema(entree, resultat, cartouche=cartouche or {})
    svg = _svg_avec_blocs_edites(svg, places,
                                 {bloc.clef: bloc for bloc in origine})
    return {'svg': svg, 'blocs': _blocs_publies(places, edition),
            'liaisons': _liaisons(places), 'largeur': largeur,
            'hauteur': hauteur}
