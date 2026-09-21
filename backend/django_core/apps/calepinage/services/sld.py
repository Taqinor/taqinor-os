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

CALX234 — LES POSITIONS, ET LA PORTE D'ÉCRITURE
------------------------------------------------
``rendre_schema(entree, resultat, cartouche, positions, standard)`` accepte
DEPUIS TOUJOURS une surcharge de position par organe, et ``_positions`` sait
la consommer : la capacité existait sans être atteignable. Le chemin
CALEPINAGE appelle donc le moteur DIRECTEMENT, avec ses positions — il cesse
de passer par la porte cross-app ``apps/ventes/selectors.py::
schema_unifilaire_svg``, qui reste INTACTE (octet pour octet) pour le chemin
``devis=``. Une position hors planche est refusée en nommant la clef et la
borne du format.

CALX237 — UN GABARIT PAR PAYS, SANS SUPPOSER UNE NORME AU MAROC
----------------------------------------------------------------
Les seules références que les organes citent sont françaises (NF C 15-100,
UTE C 15-712-1, IEC 62548) et ``services/norme.py`` OMET déjà tout calcul
qui en dépend quand aucune norme n'est choisie. ``gabarit_de_schema`` en
tire la conséquence sur le DESSIN : gabarit ``fr`` (la chaîne d'aujourd'hui,
inchangée), gabarit ``societe`` (la société a nommé le texte qui la fonde),
et — à défaut — gabarit ``neutre`` : la planche passe en mode TOPOLOGIE
(``standard=True``, aucun calibre ni section) et porte un bandeau qui NOMME
le réglage manquant. Aucun gabarit marocain n'est inventé : il n'existe
aucun texte normatif marocain dans ce dépôt.

LE DESSIN RESTE UNIQUE
----------------------
Le SVG n'est pas reconstruit ici : les blocs ÉDITÉS sont passés au moteur
(``rendre_schema(..., blocs=, bandeau=)``, API publique posée en phase 2 du
lot 4) et la planche sort d'UN seul passage, avec ses textes définitifs et
son bandeau. Ce module ne connaît plus ni la géométrie du dessin (elle est
publiée par ``core/electrique/schema.py::GEOMETRIE``), ni le placement (par
``places_du_schema``) : aucune seconde géométrie, aucune réémission de
fragment, aucun filtre de texte sur le SVG rendu.
"""
from __future__ import annotations

import re

__all__ = [
    'CLE_EDITION', 'RUBRIQUES', 'LONGUEUR_TEXTE_MAX', 'MOTS_D_ARGENT',
    'GABARIT_FR', 'GABARIT_SOCIETE', 'GABARIT_NEUTRE',
    'SldRefuse', 'branches_onduleur_de_la_conception',
    'cartouche_du_calepinage', 'edition_sld', 'enregistrer_edition_sld',
    'gabarit_de_schema', 'rendu_du_schema', 'schema_du_calepinage',
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


#: Les trois gabarits de planche (CALX237). Il n'y a PAS de gabarit
#: marocain : aucun texte normatif marocain n'est présent dans ce dépôt, et
#: NF C 15-100 / UTE C 15-712-1 ne s'impriment pas sur un chantier qui ne les
#: a pas choisies (décision fondateur D1, ``services/norme.py``).
GABARIT_FR = 'fr'
GABARIT_SOCIETE = 'societe'
GABARIT_NEUTRE = 'neutre'

#: Le bandeau du gabarit NEUTRE : il DIT ce qui est omis et NOMME le réglage
#: à renseigner (règle fondateur « erreur → champ fautif »).
BANDEAU_NEUTRE = (
    "Calibres et sections OMIS%s : aucune norme électrique n'est choisie — "
    "renseignez « Norme électrique » dans les réglages du module. Cette "
    "planche ne montre que la topologie : désignations, quantités, repères."
)


class SldRefuse(ValueError):
    """Une édition de schéma refusée, avec un message FRANÇAIS.

    ``champ`` porte le chemin de la saisie fautive tel que le contrat le
    décrit (``edition.positions.coffret_ac``) : l'écran pointe LE champ, il
    n'affiche pas un « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


# ──────────────────────────────── CALX237 — le GABARIT de planche, par pays
def _references_du_gabarit(norme):
    """Les textes cités, TIRÉS du verdict de norme — jamais recopiés ici.

    La référence de la norme d'abord, puis celles que chaque coefficient
    publié porte déjà (``services/norme.py::coefficients_publies``). Rien
    n'est ajouté : un gabarit ne cite que ce que la société ou le noyau a
    réellement déclaré.
    """
    references = []
    principale = (norme.get('reference') or '').strip()
    if principale:
        references.append(principale)
    for coefficient in (norme.get('coefficients') or {}).values():
        texte = (coefficient or {}).get('reference')
        texte = (texte or '').strip()
        if texte and texte not in references:
            references.append(texte)
    return tuple(references)


def gabarit_de_schema(norme):
    """CALX237 — QUEL gabarit de planche, et ce qu'il omet sans norme.

    Args:
        norme: le verdict de ``services/norme.py::norme_applicable``.

    Returns:
        ``{code, libelle, norme, reference, references, pays, standard,
        bandeau, motif}``.

    Trois cas, et AUCUN gabarit marocain :

    * **``fr``** — le jeu français est applicable : la chaîne dessinée est
      celle d'aujourd'hui, inchangée, et le gabarit cite les textes que le
      moteur cite déjà (NF C 15-100 / UTE C 15-712-1 / IEC 62548).
    * **``societe``** — la société a DÉCLARÉ sa norme en nommant le texte qui
      la fonde (``services/norme.py`` refuse déjà une norme sans référence) :
      même dessin, gabarit nommé d'après ce texte.
    * **``neutre``** — aucune norme choisie : la planche bascule en mode
      TOPOLOGIE (``standard=True`` du moteur : désignations, quantités,
      repères ; aucun calibre, aucune section) et porte un bandeau qui dit
      pourquoi. Aucun symbole ni texte marocain n'est inventé — il n'en
      existe aucun dans ce dépôt.
    """
    from .norme import NORME_FRANCAISE

    norme = norme if isinstance(norme, dict) else {}
    pays = (norme.get('pays') or '').strip()
    if not norme.get('applicable'):
        return {
            'code': GABARIT_NEUTRE,
            'libelle': 'Gabarit neutre — topologie seule',
            'norme': None,
            'reference': '',
            'references': (),
            'pays': pays,
            'standard': True,
            'bandeau': BANDEAU_NEUTRE % (
                ' pour le pays « %s »' % pays if pays else ''),
            'motif': norme.get('motif') or '',
        }
    choisie = norme.get('norme') or ''
    reference = (norme.get('reference') or '').strip()
    if choisie == NORME_FRANCAISE:
        code = GABARIT_FR
        libelle = 'Gabarit français — %s' % reference
    else:
        code = GABARIT_SOCIETE
        libelle = 'Gabarit déclaré par la société — %s' % reference
    return {
        'code': code,
        'libelle': libelle,
        'norme': choisie,
        'reference': reference,
        'references': _references_du_gabarit(norme),
        'pays': pays,
        'standard': False,
        'bandeau': '',
        'motif': norme.get('motif') or '',
    }


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
    """CALX234 — la FORME, puis les BORNES de la planche réellement dessinée.

    Les bornes sont celles du format retenu par le moteur pour CETTE
    conception (A4 ou A3 paysage, ``core/electrique/schema.py``), moins
    l'encombrement d'une boîte : une position qui laisse le bloc à cheval sur
    le bord donnerait une planche tronquée à l'impression. Le refus NOMME la
    clef et la borne dépassée.
    """
    from core.electrique.schema import GEOMETRIE

    clef = champ.rsplit('.', 1)[-1]
    point = _point_lisible(brut)
    if point is None:
        raise SldRefuse(
            "La position de « %s » doit être un objet { x, y } en points de "
            "planche." % clef, champ=champ)
    largeur = dessin.get('largeur')
    hauteur = dessin.get('hauteur')
    if not largeur or not hauteur:
        return point
    bornes = (('x', largeur - GEOMETRIE.bloc_l),
              ('y', hauteur - GEOMETRIE.bloc_h))
    for axe, maximum in bornes:
        if point[axe] < 0.0 or point[axe] > maximum:
            raise SldRefuse(
                "La position de « %s » sort de la planche : %s doit rester "
                "entre 0 et %s points (planche %s × %s, boîte d'organe "
                "comprise)." % (clef, axe, _nombre(maximum),
                                _nombre(largeur), _nombre(hauteur)),
                champ=champ)
    return point


def _nombre(valeur):
    """Un nombre de planche, au dixième, sans zéro inutile."""
    return ('%.1f' % float(valeur)).rstrip('0').rstrip('.')


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
                           edition=edition_sld(calepinage),
                           gabarit=_gabarit_du_calepinage(calepinage))


def _gabarit_du_calepinage(calepinage):
    """Le gabarit applicable à CE calepinage (CALX237), via ses réglages."""
    from .electrique import parametres_societe
    from .norme import norme_applicable

    return gabarit_de_schema(norme_applicable(
        parametres_societe(calepinage)))


# ──────────────────────────────────────────────── le dessin, édition comprise
def _places(blocs, positions):
    """Les places des blocs, PAR LE MOTEUR — jamais une seconde géométrie.

    ``core/electrique/schema.py::places_du_schema`` est l'API PUBLIQUE du
    placement (crochet posé en phase 2) : ce module ne connaît plus ni le
    format de planche, ni le serpentin, ni les organes qui pendent hors
    rangée.
    """
    from core.electrique.schema import places_du_schema

    return places_du_schema(blocs, positions)


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
    from core.electrique.schema import GEOMETRIE

    bloc_l, bloc_h = GEOMETRIE.bloc_l, GEOMETRIE.bloc_h
    serie = [place for place in places if not place[4]]
    liaisons = []
    for depart, arrivee in zip(serie, serie[1:]):
        bloc_a, xa, ya, rangee_a, _ = depart
        bloc_b, xb, yb, rangee_b, _ = arrivee
        if rangee_a == rangee_b:
            if xb >= xa:
                points = ((xa + bloc_l, ya + bloc_h / 2),
                          (xb, yb + bloc_h / 2))
            else:
                points = ((xa, ya + bloc_h / 2),
                          (xb + bloc_l, yb + bloc_h / 2))
        else:
            points = ((xa + bloc_l / 2, ya + bloc_h),
                      (xb + bloc_l / 2, yb))
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
                'points': ((ancre[1] + bloc_l / 2, ancre[2] + bloc_h),
                           (place[1] + bloc_l / 2, place[2]))})
    return tuple(liaisons)


def rendu_du_schema(entree, resultat, *, edition=None, gabarit=None,
                    cartouche=None, branches_onduleur=None):
    """Le dessin d'une conception, ÉDITION APPLIQUÉE — SVG et blocs d'accord.

    ``gabarit`` (CALX237) : le verdict de ``gabarit_de_schema``. Un gabarit
    NEUTRE bascule la planche en mode topologie (aucun calibre, aucune
    section) et lui appose son bandeau ; absent, la planche est celle
    d'aujourd'hui, inchangée.

    ``branches_onduleur`` (CALX238, crochet de phase 2) : les branches
    d'onduleur de l'installation. Plusieurs exemplaires IDENTIQUES se replient
    en « typique de N » au lieu d'être dessinés N fois ; absentes — ou une
    seule — la planche est celle d'aujourd'hui, octet pour octet.

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
    standard = bool((gabarit or {}).get('standard'))
    origine = blocs_du_schema(
        entree, resultat, standard=standard,
        branches_onduleur=branches_onduleur or None)
    blocs = _blocs_edites(origine, edition)
    positions = edition['positions'] or None
    places, largeur, hauteur = _places(blocs, positions)
    # CALX234 — le chemin CALEPINAGE appelle le moteur DIRECTEMENT, avec ses
    # positions forcées : la porte cross-app ``apps.ventes.selectors.
    # schema_unifilaire_svg`` n'en porte pas le paramètre et reste intacte,
    # octet pour octet, pour le chemin ``devis=``.
    #
    # CALX233 (crochet de phase 2) — les blocs ÉDITÉS partent au moteur, qui
    # rend la planche en UN passage avec les textes définitifs : la
    # recomposition du SVG rendu a disparu, et avec elle le seul endroit du
    # module qui réémettait un fragment de dessin.
    svg = rendre_schema(entree, resultat, cartouche=cartouche or {},
                        positions=positions, standard=standard, blocs=blocs,
                        bandeau=(gabarit or {}).get('bandeau') or '')
    return {'svg': svg, 'blocs': _blocs_publies(places, edition),
            'liaisons': _liaisons(places), 'largeur': largeur,
            'hauteur': hauteur}


def branches_onduleur_de_la_conception(conception):
    """CALX238 — les branches d'onduleur de CETTE conception, ou ``()``.

    Le noyau dimensionne un MODÈLE et un NOMBRE (``evaluer_onduleurs``) : les
    exemplaires sont donc IDENTIQUES, et c'est tout ce qu'on peut en dire.
    Chaque branche ne porte donc QUE son modèle — ni nombre de chaînes, ni
    longueurs, ni organes par exemplaire : le moteur ne rattache aucune
    chaîne à un exemplaire d'onduleur (``services/chaines.py`` le dit en
    toutes lettres), et remplir ces champs serait les inventer (D-CALX 7).

    Des branches IDENTIQUES se replient exactement en « typique de N », ce
    qui est la seule chose que CALX238 avait à obtenir. UN SEUL onduleur ⇒
    aucune branche : la planche est celle d'aujourd'hui, octet pour octet.
    """
    from .chaines import evaluer_onduleurs

    evaluation = evaluer_onduleurs(conception)
    nombre = int(getattr(evaluation, 'nombre', 0) or 0)
    if nombre <= 1:
        return ()
    onduleur = getattr(getattr(conception, 'entree', None), 'onduleur', None)
    modele = getattr(onduleur, 'designation', '') or ''
    return tuple({'modele': modele} for _rang in range(nombre))


# ────────────────────────────────── CALX234 — la réponse servie par la vue
def cartouche_du_calepinage(calepinage):
    """Le cartouche technique de CE calepinage : client, référence, date.

    ``rendre_schema`` n'accepte aucun autre champ, et aucun montant n'y a sa
    place — c'est une pièce qui part au bureau de contrôle, pas une offre
    (D-CALX 5). La date est celle de CRÉATION telle qu'elle est stockée,
    jamais une date de rendu : deux impressions du même dossier portent le
    même cartouche.
    """
    cree_le = getattr(calepinage, 'created_at', None)
    return {
        'client': getattr(getattr(calepinage, 'client', None), 'nom', '')
        or '',
        'reference': getattr(calepinage, 'titre', '') or '',
        'date': cree_le.strftime('%d/%m/%Y') if cree_le else '',
    }


def _edition_publiee(edition, dessin):
    """L'édition RÉDUITE aux blocs réellement dessinés.

    ``edition`` n'est jamais une seconde source de vérité du dessin (contrat
    CALX204) : une clef persistée que la conception ne retient plus — un
    parafoudre retiré depuis — ne peut pas être publiée comme une édition
    active, puisque aucun bloc ne la porterait. Elle reste STOCKÉE (le jour
    où l'organe revient, son libellé revient avec lui) et le ``POST``, lui,
    la refuse en la nommant.
    """
    clefs = {bloc['clef'] for bloc in dessin.get('blocs') or ()}
    publiee = _edition_vide()
    for rubrique in RUBRIQUES:
        publiee[rubrique] = {clef: valeur
                             for clef, valeur in edition[rubrique].items()
                             if clef in clefs}
    return publiee


def schema_du_calepinage(calepinage):
    """CALX204 — les SIX clés du contrat, dans tous les états.

    ``svg`` vaut ``None`` quand la conception ne permet pas de dessiner
    (fiche muette ou bloquant) : mêmes portails que l'annexe technique du
    devis, et la réponse DIT pourquoi par ``bloquants``/``manquantes``, les
    libellés français du service électrique tels quels. Aucune clé ne
    disparaît jamais (leçon PACT10 du 03/08/2026).
    """
    from .electrique import bloquants_nommes, conception_du_calepinage

    conception, _materiel, _donnees, _document = conception_du_calepinage(
        calepinage)
    manquantes = list(getattr(conception, 'manquantes', ()) or ())
    bloquants = list(bloquants_nommes(conception) or ())
    reponse = {
        'calepinage': getattr(calepinage, 'pk', None),
        'svg': None,
        'blocs': [],
        'edition': _edition_vide(),
        'bloquants': bloquants,
        'manquantes': manquantes,
    }
    if manquantes or bloquants:
        return reponse
    edition = edition_sld(calepinage)
    dessin = rendu_du_schema(
        getattr(conception, 'entree', None),
        getattr(conception, 'resultat', None),
        edition=edition,
        gabarit=_gabarit_du_calepinage(calepinage),
        cartouche=cartouche_du_calepinage(calepinage),
        # CALX238 (crochet de phase 2) — dix onduleurs identiques dessinent
        # UN sous-ensemble « typique de 10 », et la planche cesse de basculer
        # en A3 par le seul effet du nombre.
        branches_onduleur=branches_onduleur_de_la_conception(conception))
    reponse['svg'] = dessin['svg']
    reponse['blocs'] = [dict(bloc) for bloc in dessin['blocs']]
    reponse['edition'] = _edition_publiee(edition, dessin)
    return reponse
