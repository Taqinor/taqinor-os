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


# ── QJR85 — `appliquer()` : L'ORDRE UNIQUE DES HUIT ÉTAPES ──────────────────
#
# Constat QB85 (audit L3 du 29/08/2026) : les CINQ origines d'un devis
# enchaînent les mêmes étapes, mais chacune dans SON ordre, avec SES oublis.
# Ce n'est pas une divergence de règles — les règles, elles, viennent d'être
# rendues communes (QJR80 `composer`, QJR82 `verifier`, QJR83/QJR84
# `ecrire_lignes`, QJR62 `ecrire_etude_params`, L-1V `rafraichir_etudes`) —
# c'est une divergence d'ORDONNANCEMENT. Et un ordonnancement qui diverge
# produit des devis qui divergent : QJR20 a documenté le cas le plus cher, où
# les quatre études repartaient de la composition d'AVANT parce que personne
# n'avait relu l'instance verrouillée.
#
# ``appliquer`` est donc DÉLIBÉRÉMENT SANS RÈGLE PROPRE : elle ne compose pas,
# ne dimensionne pas, ne tarife pas. Elle APPELLE, dans l'ordre, huit étapes
# déjà en service, et c'est tout ce qu'elle fait. C'est ce qui la rend
# relisable, et c'est ce qui rendra chaque bascule (M5) vérifiable par un
# simple golden.
#
# AUCUN DES CINQ CHEMINS NE L'APPELLE ENCORE — c'est voulu, et c'est la
# condition de sûreté de cette vague : la fonction est posée, testée, et les
# bascules sont M5 (QJR93 et suivantes), une par une, chacune avec son golden.

#: QJR85 — les CINQ origines d'un devis. Elles ne changent AUCUNE règle : elles
#: nomment d'où vient la demande (journal, propriétaire d'étude, message).
ORIGINE_ECRAN = 'ecran'
ORIGINE_CALEPINAGE = 'calepinage'
ORIGINE_AUTO = 'auto'
ORIGINE_TUNNEL = 'tunnel'
ORIGINE_RESYNCHRONISATION = 'resynchronisation'
ORIGINES = (ORIGINE_ECRAN, ORIGINE_CALEPINAGE, ORIGINE_AUTO,
            ORIGINE_TUNNEL, ORIGINE_RESYNCHRONISATION)

#: LES HUIT ÉTAPES, dans l'ordre, nommées UNE fois. Le journal rendu par
#: ``appliquer`` les liste dans l'ordre où elles ont réellement tourné : c'est
#: ce que le test d'ordre assertit, et ce qu'une bascule pourra comparer.
ETAPES = ('resoudre_entrees', 'decider_taille', 'composer', 'verifier',
          'ecrire_lignes', 'ecrire_etude_params', 'rafraichir_etudes',
          'finaliser')


@dataclass(frozen=True)
class CibleDevis:
    """Le CHAMP PV arrêté par l'étape 2 — ce que le devis va vendre.

    GELÉ : une cible arrêtée ne se retouche pas en cours de pipeline ; on en
    dérive une autre (``dataclasses.replace``) si un plafond de toit mord.
    """

    nb_panneaux: int = 0
    panel_watt: object = None
    kwc: float = 0.0
    source: str = ''
    dimensionnement_avec: object = None


@dataclass(frozen=True)
class IntentionDevis:
    """LE jeu de paramètres du pipeline entier — un seul, pour les cinq
    origines. GELÉ, pour la même raison qu'``IntentionComposition``.

    * ``origine`` — laquelle des cinq (``ORIGINES``) ;
    * ``company`` / ``user`` — jamais lus d'un corps de requête ;
    * ``lead`` / ``client`` — au moins un des deux ; le client se résout depuis
      le lead par ``crm.services.resolve_client_for_lead``, jamais ici ;
    * ``mode_installation`` — le marché (``Devis.ModeInstallation``) ;
    * ``entrees`` — un ``EntreesMoteur`` DÉJÀ lu, quand l'appelant l'a
      (l'étape 1 le relit sinon) ;
    * ``cible`` — une ``CibleDevis`` DÉJÀ arrêtée, quand l'appelant l'a
      (l'étape 2 la demande au moteur horaire sinon). C'est ce qui permet à
      l'écran et au calepinage — où le commercial a DÉJÀ tranché — de ne pas
      se faire redimensionner sous les pieds ;
    * ``scenario`` — ``'sans'`` / ``'avec'`` / ``'les_deux'`` ; vide ⇒
      ``'les_deux'`` (le défaut fondateur U2) ;
    * ``layout`` — le calepinage 3D, quand il y en a un ;
    * ``overrides`` — le patch de surcharges déclarées (QJR58), appliqué par
      ``domain/overrides`` — jamais réinventé ici ;
    * ``exact`` — la cible vient d'un NOMBRE TAPÉ, pas d'un toit : les deux
      options y sont portées à la hausse comme à la baisse (cf.
      ``sync_devis_from_layout(cible_exacte=...)``).
    """

    origine: str
    company: object
    user: object = None
    lead: object = None
    client: object = None
    mode_installation: str = 'residentiel'
    entrees: object = None
    cible: object = None
    scenario: str = ''
    layout: object = None
    overrides: object = None
    exact: bool = False
    taux_tva: Decimal = Decimal('20')
    remise_globale: Decimal = Decimal('0')
    structure_type: str = 'acier'
    mppt_paires: int = 1
    phase: object = None
    gamme_nom_devis: object = None


def _scenario_de(intention):
    """Le scénario du pipeline : celui de l'intention, sinon LES DEUX (U2)."""
    demande = (intention.scenario or '').strip().lower()
    return demande if demande in SCENARIOS_COMPOSABLES else COMPOSITION_LES_DEUX


def resoudre_entrees(devis, intention):
    """Étape 1 — LES ENTRÉES du moteur, lues UNE fois et par une seule
    fonction (``domain/entrees``, QJR42/QJR43).

    L'intention peut les porter déjà lues (l'appelant vient de les afficher) :
    on ne relit alors rien — deux lectures donneraient deux dimensionnements.
    """
    if intention.entrees is not None:
        return intention.entrees
    if devis is not None and getattr(devis, 'pk', None) is not None:
        return entrees_depuis_devis(devis)
    if intention.lead is not None:
        return entrees_depuis_lead(intention.lead, intention.company)
    return None


def decider_taille(intention, entrees):
    """Étape 2 — LE CHAMP PV.

    Le pipeline NE REDIMENSIONNE PAS de sa propre initiative : une cible déjà
    arrêtée par l'appelant (écran, calepinage, puissance demandée) est
    SOUVERAINE. À défaut, et seulement à défaut, le moteur horaire tranche —
    le seul dimensionneur, ordre fondateur du 29/08/2026 (« ALL sizing should
    go through the new sizing tool ») — et son refus est NOMMÉ, jamais remplacé
    par un repli forfaitaire.
    """
    if intention.cible is not None:
        return intention.cible
    if intention.lead is None:
        return None
    nb_panneaux, watt, source, avec = _panneaux_dimensionnement_horaire(
        lead=intention.lead, company=intention.company,
        phase=phase_client_pour_dimensionnement(intention.lead))
    if nb_panneaux <= 0:
        raise _refus_dimensionnement(source)
    watt = watt or _AUTO_PANEL_WATT
    return CibleDevis(
        nb_panneaux=nb_panneaux, panel_watt=watt,
        kwc=round(nb_panneaux * float(watt) / 1000.0, 2),
        source=source, dimensionnement_avec=avec)


def intention_de_composition(intention, cible, *, avertissements=None):
    """Traduit l'intention de devis en intention de COMPOSITION (étapes 3-4).

    Pure traduction : aucun choix n'est fait ici, tout vient de l'intention ou
    de la cible que l'étape 2 a arrêtée.
    """
    cible = cible or CibleDevis()
    return IntentionComposition(
        company=intention.company,
        kwc=cible.kwc,
        nb_panneaux=cible.nb_panneaux,
        panel_watt=cible.panel_watt,
        scenario=_scenario_de(intention),
        structure_type=intention.structure_type,
        taux_tva=intention.taux_tva,
        mppt_paires=intention.mppt_paires,
        phase=intention.phase,
        gamme_nom_devis=intention.gamme_nom_devis,
        dimensionnement_avec=cible.dimensionnement_avec,
        avertissements=avertissements,
    )


def ecrire_lignes(devis, composition, *, company, avertissements=None):
    """Étape 5 — les lignes, par L'ÉCRIVAIN UNIQUE (QJR73 + QJR84).

    L'ordre VOULU est posé EXPLICITEMENT (``ordre=index``), jamais laissé au
    tri de repli sur ``id`` : sans lui l'ordre par défaut de la société (PVORD)
    ne survivrait pas à la première renumérotation. La re-tarification des
    forfaits au panneau (QJR83) est faite par l'écrivain lui-même.
    """
    lignes_in = [
        {
            'produit': getattr(spec.produit, 'id', None),
            'designation': spec.designation,
            'quantite': str(spec.quantite),
            'prix_unitaire': str(spec.prix_unitaire),
            'ordre': index,
            'variante': getattr(spec, 'variante', '') or '',
        }
        for index, spec in enumerate(composition or ())
    ]
    return remplacer_lignes(devis, lignes_in, company,
                            avertissements=avertissements)


def ecrire_etude_params(devis, intention, composition):
    """Étape 6 — l'étude, par L'ÉCRIVAIN UNIQUE d'``etude_params`` (QJR62).

    Le pipeline n'écrit ici que ce qu'il vient lui-même d'arrêter : le
    SCÉNARIO réellement servable par les lignes (même garde anti-mensonge que
    ``_scenario_stocke`` — « Les deux » exige les deux onduleurs ET la
    batterie) et, quand un calepinage est fourni, la production et les
    économies qu'il porte. Le kWc, lui, a un propriétaire séparé
    (``poser_puissance_kwc``, QJR63) : il est posé à l'étape 8, sur les lignes
    RÉELLEMENT écrites.
    """
    a_batterie = any(_is_battery(s.designation) for s in (composition or ()))
    a_hybride = any(_is_hybrid_inverter(s.designation)
                    for s in (composition or ()))
    a_reseau = any(_is_reseau_inverter(s.designation)
                   for s in (composition or ()))
    if (_scenario_de(intention) == COMPOSITION_LES_DEUX
            and a_reseau and a_hybride and a_batterie):
        scenario = SCENARIO_LES_DEUX
    else:
        scenario = _scenario_stocke(a_batterie and a_hybride)

    cles = {'scenario': scenario}
    resultat = (intention.layout or {}).get('result') or {}
    if resultat.get('annualKwh') is not None:
        cles['production_annuelle'] = int(resultat['annualKwh'])
    if resultat.get('savings') is not None:
        cles['economies_annuelles'] = int(resultat['savings'])
    return ecrire_etude(devis, proprietaire=CALEPINAGE, **cles)


def rafraichir_etudes(verrou):
    """Étape 7 — LES QUATRE études, sur l'instance VERROUILLÉE **ET RELUE**.

    QJR20 (29/08/2026) — LA RELECTURE N'EST PAS UNE PRÉCAUTION, C'EST L'ÉTAPE.
    Les quatre études repartent des LIGNES du devis ; l'instance que le
    pipeline tient a été chargée AVANT l'écriture (et, côté viewset, avec un
    ``prefetch_related('lignes')``). Sans relecture, elles recalculent sur la
    composition d'AVANT et RÉÉCRIVENT ``etude_params`` par-dessus ce que les
    étapes 5-6 viennent d'y poser — la conception électrique, seule des quatre
    à n'être jamais recalculée à la lecture, PERSISTE alors un schéma faux.

    ``refresh_from_db()`` sans ``fields`` vide déjà
    ``_prefetched_objects_cache`` (Django) ; le vidage explicite est une
    ceinture, pour que ce contrat ne dépende pas d'un détail du framework.
    """
    verrou.refresh_from_db()
    verrou._prefetched_objects_cache = {}
    return rafraichir_etudes_du_devis(verrou)


def finaliser(devis, intention):
    """Étape 8 — le kWc par son propriétaire, la marge interne, le schéma.

    Les trois sont BEST-EFFORT et n'annulent jamais un devis écrit :
    ``poser_puissance_kwc`` (QJR63 — le kWc vient des LIGNES, pas du layout),
    ``refresh_marge_snapshot`` (QX23be, manager-only) et
    ``concevoir_electrique_du_devis`` (PV42).
    """
    poser_puissance_kwc(devis)
    refresh_marge_snapshot(devis)
    concevoir_electrique_du_devis(devis, origine=intention.origine)
    return devis


def _verrouiller(devis):
    """Recharge le devis sous ``select_for_update`` — l'instance que le
    pipeline écrit, et la seule que l'étape 7 relit."""
    from apps.ventes.models import Devis

    return Devis.objects.select_for_update().get(pk=devis.pk)


def _creer_brouillon(intention):
    """Le devis n'existe pas encore : on le crée BROUILLON, avec la
    numérotation anti-collision (``core.numbering``, JAMAIS count()+1).

    Le client est résolu depuis le lead par ``crm.services`` — la frontière
    cross-app sanctionnée, jamais un import de ``crm.models``.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference

    client = intention.client
    if client is None:
        if intention.lead is None:
            raise ValueError(
                'appliquer() exige un lead ou un client pour créer un devis.')
        from apps.crm.services import resolve_client_for_lead
        client = resolve_client_for_lead(intention.lead)

    def _create(reference):
        return Devis.objects.create(
            company=intention.company, reference=reference,
            client=client, lead=intention.lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=intention.taux_tva,
            remise_globale=intention.remise_globale,
            created_by=intention.user,
            mode_installation=intention.mode_installation,
            roof_layout=intention.layout or None,
        )

    return create_with_reference(Devis, 'DEV', intention.company, _create)


def appliquer(devis, intention):
    """QJR85 — L'ORDRE UNIQUE des huit étapes. AUCUNE règle nouvelle.

    ``devis`` peut être ``None`` : le pipeline crée alors un BROUILLON (aucun
    statut aval n'est jamais touché — règle #4). Sinon il VERROUILLE le devis
    reçu et travaille sur l'instance verrouillée.

    Rend un dict ``{'devis', 'etapes', 'entrees', 'cible', 'composition',
    'avertissements'}``. ``etapes`` liste les étapes DANS L'ORDRE OÙ ELLES ONT
    RÉELLEMENT TOURNÉ — c'est le contrat que le test assertit, et ce qu'une
    bascule (M5) pourra comparer à l'ancien chemin.

    Lève ``AutoDevisError`` quand l'étape 4 refuse : refuser AVANT d'écrire
    vaut mieux que créer puis effacer (un devis effacé rendrait sa référence
    au compteur, et le numéro suivant la reprendrait).

    **AUCUN des cinq chemins n'appelle encore cette fonction** (QJR85) : les
    bascules sont M5, une par une, chacune avec son golden.
    """
    if intention.origine not in ORIGINES:
        raise ValueError(
            'Origine de devis inconnue « %s » — attendu : %s.'
            % (intention.origine, ', '.join(ORIGINES)))

    journal = []
    avertissements = []

    entrees = resoudre_entrees(devis, intention)
    journal.append('resoudre_entrees')

    cible = decider_taille(intention, entrees)
    journal.append('decider_taille')

    intention_compo = intention_de_composition(
        intention, cible, avertissements=avertissements)
    composition = composer(intention_compo)
    journal.append('composer')

    refus = verifier(intention_compo)
    journal.append('verifier')
    if refus:
        raise AutoDevisError(refus[0], field='composition')

    verrou = _verrouiller(devis) if devis is not None else _creer_brouillon(
        intention)

    ecrire_lignes(verrou, composition, company=intention.company,
                  avertissements=avertissements)
    journal.append('ecrire_lignes')

    ecrire_etude_params(verrou, intention, composition)
    journal.append('ecrire_etude_params')

    rafraichir_etudes(verrou)
    journal.append('rafraichir_etudes')

    finaliser(verrou, intention)
    journal.append('finaliser')

    return {
        'devis': verrou,
        'etapes': journal,
        'entrees': entrees,
        'cible': cible,
        'composition': composition,
        'avertissements': avertissements,
    }


# ── PONTS M3/M4 : noms hébergés ailleurs ─────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.bordereau import (  # noqa: E402,F401
    concevoir_electrique_du_devis,
)
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _is_battery,
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
from apps.ventes.domain.entrees import (  # noqa: E402,F401
    entrees_depuis_devis,
    entrees_depuis_lead,
)
from apps.ventes.domain.etude_schema import CALEPINAGE  # noqa: E402,F401
from apps.ventes.domain.etude_schema import ecrire as ecrire_etude  # noqa: E402,F401,E501
from apps.ventes.domain.etudes import (  # noqa: E402,F401
    rafraichir_etudes_du_devis,
    refresh_marge_snapshot,
)
from apps.ventes.domain.lignes import remplacer_lignes  # noqa: E402,F401
from apps.ventes.domain.scenario import (  # noqa: E402,F401
    SCENARIO_LES_DEUX,
    _scenario_stocke,
    poser_puissance_kwc,
)
from apps.ventes.domain.taille import (  # noqa: E402,F401
    _AUTO_PANEL_WATT,
    AutoDevisError,
    _panneaux_dimensionnement_horaire,
    _refus_dimensionnement,
    phase_client_pour_dimensionnement,
)

__all__ = [
    'COMPOSITION_AVEC',
    'COMPOSITION_LES_DEUX',
    'COMPOSITION_SANS',
    'ETAPES',
    'ORIGINES',
    'ORIGINE_AUTO',
    'ORIGINE_CALEPINAGE',
    'ORIGINE_ECRAN',
    'ORIGINE_RESYNCHRONISATION',
    'ORIGINE_TUNNEL',
    'CibleDevis',
    'IntentionComposition',
    'IntentionDevis',
    'MSG_AUCUN_PANNEAU',
    'MSG_SANS_BATTERIE',
    'MSG_SANS_ONDULEUR_HYBRIDE',
    'MSG_SANS_ONDULEUR_RESEAU',
    'SCENARIOS_COMPOSABLES',
    'appliquer',
    'composer',
    'decider_taille',
    'ecrire_etude_params',
    'ecrire_lignes',
    'estampiller_variante',
    'finaliser',
    'intention_de_composition',
    'message_batterie_incompatible',
    'rafraichir_etudes',
    'resoudre_entrees',
    'verifier',
]
