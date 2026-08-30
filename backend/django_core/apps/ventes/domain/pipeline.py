# -*- coding: utf-8 -*-
"""``apps.ventes.domain.pipeline`` — LES ÉTAPES du parcours devis.

Le parcours devis a CINQ origines (l'écran générateur, le calepinage 3D, le
devis automatique depuis un lead, le tunnel du site, la resynchronisation) et,
jusqu'à M4, chacune recomposait à sa façon. Ce module est l'endroit où les
étapes deviennent COMMUNES, une par une, sans big-bang :

    resoudre_entrees → decider_taille → composer → verifier
        → ecrire_lignes → ecrire_etude_params → rafraichir_etudes
        → marge_snapshot + conception électrique

QJR80 pose la TROISIÈME étape, ``composer``, et elle seule. Les autres étapes
existent déjà, à leur place (``domain/entrees``, ``domain/taille``,
``domain/geometrie``, ``domain/lignes``, ``domain/etude_schema``,
``domain/etudes``) ; leur ORDONNANCEMENT est QJR85, les bascules des cinq
chemins sont M5. Rien ici n'appelle un chemin : ce sont les chemins qui
appellent ici.

RÈGLE D'IMPORT (cf. ``domain/__init__.py``) : les noms lus dans d'autres
modules de ``domain/`` sont importés EN BAS de ce fichier, en visant le module
qui porte le corps — jamais la façade ``services.py``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from dataclasses import dataclass
from decimal import Decimal
import logging

logger = logging.getLogger("apps.ventes.services")


# ── Étape 3 — COMPOSER ───────────────────────────────────────────────────────
# Le constat QB80 (audit L3 du 29/08/2026) : ``composer_devis_residentiel``
# (le dry-run que le vendeur APPROUVE) et ``build_devis_from_layout`` (ce qui
# est RÉELLEMENT créé) enrobaient tous deux ``composition_residentielle`` mais
# lui passaient des jeux de paramètres DIFFÉRENTS — la création n'acceptait ni
# ne transmettait ``mppt_paires`` ni ``structure_type``. L'aperçu pouvait donc
# montrer les mètres de câble DC de trois paires de MPPT et des structures
# ALUMINIUM là où le devis créé facturait une paire et de l'ACIER. Ce ne sont
# pas des détails : c'est du câble au mètre et un matériau de structure, tous
# deux facturés au client.
#
# Le correctif structurel est un SEUL jeu de paramètres, nommé une fois ici, et
# deux appelants qui le remplissent. Un troisième paramètre ajouté dans six
# mois le sera POUR LES DEUX chemins — c'est exactement la propriété qu'on
# achète.

#: Les trois scénarios qu'une composition résidentielle sait servir. Mêmes
#: valeurs que ``SCENARIOS_DEMANDABLES`` (``domain/creation``), volontairement
#: redéclarées ici : ``pipeline`` ne doit pas dépendre de ``creation``, qui
#: l'appelle.
COMPOSITION_SANS = 'sans'
COMPOSITION_AVEC = 'avec'
COMPOSITION_LES_DEUX = 'les_deux'
SCENARIOS_COMPOSABLES = (COMPOSITION_SANS, COMPOSITION_AVEC,
                         COMPOSITION_LES_DEUX)


@dataclass(frozen=True)
class IntentionComposition:
    """LE jeu de paramètres de l'étape ``composer`` — un seul, pour tous.

    GELÉ (``frozen=True``) : une étape ne réécrit jamais l'intention de
    l'appelant sur place ; elle en dérive une autre (``dataclasses.replace``)
    si elle a besoin d'en changer un champ. C'est ce qui rend une composition
    REJOUABLE à l'identique, et c'est la même garantie que ``IntentionDevis``
    portera pour le pipeline entier (QJR85).

    Les valeurs par défaut sont EXACTEMENT celles de
    ``composition_residentielle`` : un appelant qui ne renseigne rien compose
    ce que ce dépôt composait déjà.

    * ``company`` — la société ; le catalogue et les règles de gamme (marques
      épinglées PVMRQ, ordre des lignes PVORD) en sont déduits ICI, une seule
      fois, pour que deux appelants ne puissent pas les résoudre autrement.
    * ``kwc`` / ``nb_panneaux`` / ``panel_watt`` — le champ PV, DÉJÀ arrêté par
      l'étape ``decider_taille`` (le pipeline ne redimensionne pas : chaque
      appelant a sa propre façon de lire un layout ou une fiche lead, et c'est
      LÀ que cette lecture reste).
    * ``scenario`` — ``'sans'`` / ``'avec'`` / ``'les_deux'``, la SEULE façon
      de dire quelle forme composer. Les deux drapeaux historiques
      (``avec_batterie`` / ``deux_options``) en sont dérivés ici : ils ne
      peuvent donc plus être posés dans une combinaison contradictoire.
    * ``structure_type`` / ``mppt_paires`` — les deux paramètres que la
      création ne transmettait pas (QB80).
    * ``phase`` — PVCOMPAT, le raccordement déclaré du client.
    * ``gamme_nom_devis`` — la gamme demandée POUR CE DEVIS-LÀ, lue par
      ``carte_marques_composition``. ``None`` ⇒ les marques par défaut de la
      société.
    * ``dimensionnement_avec`` — L-2OPT, l'optimum de l'axe AVEC BATTERIE
      (``{'nb_panneaux', 'kwc', 'batterie_kwh'}``) quand il diverge.
    * ``avertissements`` — LE canal de la composition : une liste que
      l'appelant fournit et que la composition enrichit sur place. ``None``
      (le défaut) laisse la composition sur son journal interne, comportement
      historique strictement inchangé.
    * ``variante`` — QJR81, l'OPTION dont relèvent les lignes composées
      (``''`` = commune aux deux, ``'sans'`` / ``'avec'`` = propre à
      celle-là). ``''`` (LE DÉFAUT) ⇒ lignes communes, comportement inchangé.
    """

    company: object
    kwc: float = 0.0
    nb_panneaux: int = 0
    panel_watt: object = None
    scenario: str = COMPOSITION_SANS
    structure_type: str = 'acier'
    taux_tva: Decimal = Decimal('20')
    mppt_paires: int = 1
    phase: object = None
    gamme_nom_devis: object = None
    dimensionnement_avec: object = None
    avertissements: object = None
    variante: str = ''


def composer(intention):
    """Étape 3 — LE composeur, unique, de toutes les origines résidentielles.

    Rend une ``CompositionLignes`` (une liste de ``LigneKit`` porteuse des
    métadonnées de composition) — ou une liste VIDE quand la puissance est
    nulle, exactement comme ``composition_residentielle``.

    Fonction sans écriture : elle LIT le catalogue et les réglages de gamme de
    la société, puis délègue aux deux fonctions pures de
    ``domain/composition``. Aucun devis, aucune ligne, aucun statut.
    """
    scenario = (intention.scenario or '').strip().lower()
    if scenario not in SCENARIOS_COMPOSABLES:
        raise ValueError(
            'Scénario de composition inconnu « %s » — attendu : %s.'
            % (intention.scenario, ', '.join(SCENARIOS_COMPOSABLES)))
    # Les deux drapeaux historiques, dérivés d'une SEULE source. Le couple
    # (``avec_batterie=True``, ``deux_options=True``) — que l'ancien chemin de
    # création pouvait former et qui n'a aucun effet sur les lignes composées
    # (``deux_options`` décide seul dès qu'il est vrai) — n'est plus
    # exprimable.
    avec_batterie = scenario == COMPOSITION_AVEC
    deux_options = scenario == COMPOSITION_LES_DEUX

    avec = (intention.dimensionnement_avec
            if isinstance(intention.dimensionnement_avec, dict) else None)

    company = intention.company
    commun = dict(
        panel_watt=intention.panel_watt,
        structure_type=intention.structure_type,
        taux_tva=intention.taux_tva,
        avertissements=intention.avertissements,
        # U3 — les règles de gamme vivent CÔTÉ SERVEUR et sont résolues ICI :
        # marques épinglées (PVMRQ) et ordre par défaut (PVORD).
        marques=carte_marques_composition(company, intention.gamme_nom_devis),
        ordre_lignes=ordre_lignes_societe(company),
        mppt_paires=intention.mppt_paires,
        phase=intention.phase,
    )
    catalogue = catalogue_de_la_societe(company)
    kwc = float(intention.kwc or 0)
    nb_panneaux = int(intention.nb_panneaux or 0)

    # ── L-2OPT — DEUX OPTIMISEURS quand le moteur en désigne deux ────────────
    if deux_options and avec:
        lignes = composition_deux_optimiseurs(
            catalogue,
            kwc_sans=kwc,
            nb_panneaux_sans=nb_panneaux,
            kwc_avec=avec.get('kwc'),
            nb_panneaux_avec=avec.get('nb_panneaux'),
            batterie_cible_kwh=avec.get('batterie_kwh'),
            **commun)
    else:
        lignes = composition_residentielle(
            catalogue,
            kwc=kwc,
            nb_panneaux=nb_panneaux,
            avec_batterie=avec_batterie,
            deux_options=deux_options,
            # Un devis MONO « avec » retient la capacité du même optimum ;
            # absente ⇒ la règle historique kWc/5 décide seule.
            batterie_cible_kwh=(avec.get('batterie_kwh')
                                if (avec_batterie and avec) else None),
            **commun)
    return estampiller_variante(lignes, intention.variante)


def estampiller_variante(lignes, variante):
    """QJR81 — pose ``variante`` sur une composition dont les lignes sont
    COMMUNES.

    Une composition mono-optimum rend des lignes ``variante=''`` : elles
    valent pour les DEUX options du devis. Un appelant qui compose
    délibérément POUR UNE OPTION — la réparation d'un devis « Les deux » dont
    les deux options divergent (``_completer_kit_residentiel``) — doit pouvoir
    dire de quelle option relèvent les lignes qu'il vient de composer. Sans
    cela, la ferrure ajoutée pour l'option AVEC est écrite COMMUNE, donc
    dimensionnée sur le compte de l'option SANS, et la resynchronisation PVSTR
    refuse ensuite par design de toucher une ferrure commune : l'option AVEC
    reste durablement sous-structurée et son forfait de pose par panneau
    sous-facturé.

    ``variante`` vide (LE DÉFAUT de ``IntentionComposition``) ⇒ la liste est
    rendue TELLE QUELLE, MÊME OBJET, comportement strictement inchangé. Une
    composition DÉJÀ variantée (la fusion L-2OPT, qui a distingué les deux
    options ligne à ligne) n'est JAMAIS réestampillée : l'écraser détruirait
    précisément la distinction qu'elle vient d'établir.

    ``LigneKit`` est un ``namedtuple`` — donc immuable : on reconstruit la
    liste, en reportant les métadonnées portées par ``CompositionLignes``
    (sans quoi le dry-run perdrait le wattage retenu, le kWc réel et les
    marques introuvables).
    """
    marque = (variante or '').strip()
    if not marque or not lignes:
        return lignes
    if any(getattr(ligne, 'variante', '') for ligne in lignes):
        return lignes
    estampillees = CompositionLignes(
        ligne._replace(variante=marque) for ligne in lignes)
    # Report GÉNÉRIQUE des métadonnées : on recopie le ``__dict__`` de
    # l'instance plutôt qu'une liste de noms, qui se périmerait au premier
    # attribut ajouté à la composition (``capacites_batterie_vivier`` est
    # exactement ce cas).
    estampillees.__dict__.update(getattr(lignes, '__dict__', None) or {})
    return estampillees


# ── Étape 4 — VERIFIER ───────────────────────────────────────────────────────
# Le constat QB82 (audit L3 du 29/08/2026) : la pré-vérification
# ``validate_composition_for_layout`` était (a) câblée sur UN SEUL des cinq
# chemins de création — le calepinage 3D — si bien que le devis automatique et
# le tunnel créaient des devis sans elle, et (b) MONO-SCÉNARIO : elle ne savait
# dire que « avec batterie » OU « réseau », jamais « les deux ». Un devis à deux
# options pouvait donc partir avec un seul onduleur composable, et ne servir
# qu'une des deux options qu'il promettait au client.
#
# L'étape vit désormais ICI, elle parle les TROIS scénarios, et les messages
# français n'existent qu'à UN seul endroit : le commercial lit la MÊME phrase
# quel que soit le bouton par lequel le devis est né.

#: Les messages FRANÇAIS de l'étape. Ils sont VERBATIM ceux que le chemin 3D
#: prononçait déjà (des tests les épinglent) : généraliser l'étape ne change pas
#: un mot de ce que le commercial lisait.
MSG_AUCUN_PANNEAU = (
    'Aucun panneau détecté dans le layout. '
    'Terminez le tracé du toit et relancez l\'optimiseur avant de générer.')
MSG_SANS_ONDULEUR_HYBRIDE = (
    'Aucun onduleur hybride disponible (ou sans prix) dans le catalogue. '
    'Ajoutez un onduleur hybride tarifé avant de générer ce devis.')
MSG_SANS_ONDULEUR_RESEAU = (
    'Aucun onduleur réseau disponible (ou sans prix) dans le catalogue. '
    'Ajoutez un onduleur réseau/injection tarifé avant de générer.')
MSG_SANS_BATTERIE = (
    'Aucune batterie disponible (ou sans prix) dans le catalogue. '
    'Ajoutez une batterie tarifée avant de générer ce devis.')


def message_batterie_incompatible(plage):
    """PVOND — « aucune batterie » et « aucune batterie COMPATIBLE avec cet
    onduleur » n'appellent pas le même geste : on dit lequel."""
    return ('Aucune batterie compatible tarifée pour cet onduleur '
            '(plage %s-%s V). Ajoutez une batterie compatible tarifée, '
            'ou choisissez un autre onduleur, avant de générer ce '
            'devis.' % (_v_txt(plage[0]), _v_txt(plage[1])))


def verifier(intention):
    """Étape 4 — la composition demandée est-elle SERVABLE par ce catalogue ?

    Rend ``None`` quand tout est servable, sinon la LISTE des messages
    FRANÇAIS, affichables tels quels (l'appelant décide s'il refuse ou s'il
    avertit — l'étape, elle, ne lève jamais et n'écrit rien).

    LES TROIS SCÉNARIOS, et c'est la généralisation QJR82 :

    * ``'sans'``      — il faut un onduleur RÉSEAU tarifé ;
    * ``'avec'``      — il faut un onduleur HYBRIDE tarifé ET une batterie
      COMPATIBLE de cet onduleur-là (garde PVOND pilotée par la donnée) ;
    * ``'les_deux'``  — il faut LES DEUX à la fois : sans quoi le devis promet
      au client une comparaison dont une moitié n'existe pas. C'est le cas que
      la pré-vérification mono-scénario ne savait pas exprimer, et c'est
      exactement la forme que le devis automatique compose PAR DÉFAUT.

    ``nb_panneaux`` ET ``kwc`` tous deux nuls ⇒ il n'y a rien à composer : on
    le dit d'abord, avec le message du calepinage (le seul chemin où l'absence
    de panneaux a une cause actionnable).
    """
    erreurs = []
    if (int(intention.nb_panneaux or 0) <= 0
            and float(intention.kwc or 0) <= 0):
        erreurs.append(MSG_AUCUN_PANNEAU)

    scenario = (intention.scenario or '').strip().lower()
    company = intention.company
    veut_reseau = scenario in (COMPOSITION_SANS, COMPOSITION_LES_DEUX)
    veut_stockage = scenario in (COMPOSITION_AVEC, COMPOSITION_LES_DEUX)

    if veut_reseau:
        if _pick_product(company, _is_reseau_inverter,
                         role='onduleur_reseau',
                         gamme=intention.gamme_nom_devis) is None:
            erreurs.append(MSG_SANS_ONDULEUR_RESEAU)
    if veut_stockage:
        onduleur = _pick_product(company, _is_hybrid_inverter,
                                 role='onduleur_hybride',
                                 gamme=intention.gamme_nom_devis)
        # PVOND — la batterie retenue doit entrer dans la plage batterie de
        # l'onduleur hybride EFFECTIVEMENT choisi ci-dessus.
        batterie = _pick_batterie(company, onduleur=onduleur)
        if onduleur is None:
            erreurs.append(MSG_SANS_ONDULEUR_HYBRIDE)
        if batterie is None:
            plage = _plage_batterie_de_l_onduleur(onduleur)
            if plage and plage[1] > 0:
                erreurs.append(message_batterie_incompatible(plage))
            else:
                erreurs.append(MSG_SANS_BATTERIE)
    return erreurs or None


# ── PONTS M3/M4 : noms hébergés ailleurs ─────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _is_hybrid_inverter,
    _is_reseau_inverter,
    _pick_batterie,
    _pick_product,
    _plage_batterie_de_l_onduleur,
    carte_marques_composition,
    catalogue_de_la_societe,
    ordre_lignes_societe,
)
from apps.ventes.domain.composition import (  # noqa: E402,F401
    CompositionLignes,
    _v_txt,
    composition_deux_optimiseurs,
    composition_residentielle,
)

__all__ = [
    'COMPOSITION_AVEC',
    'COMPOSITION_LES_DEUX',
    'COMPOSITION_SANS',
    'IntentionComposition',
    'MSG_AUCUN_PANNEAU',
    'MSG_SANS_BATTERIE',
    'MSG_SANS_ONDULEUR_HYBRIDE',
    'MSG_SANS_ONDULEUR_RESEAU',
    'SCENARIOS_COMPOSABLES',
    'composer',
    'estampiller_variante',
    'message_batterie_incompatible',
    'verifier',
]
