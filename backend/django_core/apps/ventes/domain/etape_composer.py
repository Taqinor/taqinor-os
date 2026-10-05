# -*- coding: utf-8 -*-
"""``apps.ventes.domain.etape_composer`` — étapes 3 et 4 du parcours devis (SPL265).

Déplacé de ``domain/pipeline.py`` : l'étape COMPOSER (QJR80, l'intention de
composition, ses réglages société, ``composer``, ``estampiller_variante``), les
SONDES DE TAILLE (QJR605, ``composer_sonde`` / ``sonder_wattage``) et l'étape
VERIFIER (QJR82, les messages ``MSG_*``, ``verifier``). La région est une
FEUILLE : elle n'importe RIEN de ``pipeline`` ; ``pipeline.appliquer`` lit
``composer`` / ``verifier`` d'ici, en bas de son fichier.

RÈGLE D'IMPORT (cf. ``domain/__init__.py``) : les noms lus dans d'autres
modules de ``domain/`` sont importés EN BAS de ce fichier, en visant le module
qui porte le corps — jamais la façade ``services.py``. Déplacement pur : corps
octet-identiques, prouvé par ``tests/golden/split_dm_comp.json``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
import dataclasses
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
    * ``structure_produit_id`` — STKCAT1/STKCAT7, LE PRODUIT de structure
      choisi (id ``stock.Produit``). PRIORITAIRE sur ``structure_type``, qui
      n'est plus qu'un ALIAS DÉPRÉCIÉ ; ``None`` (LE DÉFAUT) ⇒ composition
      strictement inchangée.
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
    * ``hors_reseau`` — QJR-OFFGRID, le site est ISOLÉ (aucun raccordement) :
      onduleur AUTONOME + batterie obligatoire, forme mono-option. ``False``
      (LE DÉFAUT) ⇒ composition et vérification strictement inchangées.
    * ``ville`` — QJR604, la ville de calcul du barème transport, résolue UNE
      fois côté serveur depuis le lead (``transport.ville_du_lead``) ; ``''``
      (LE DÉFAUT) ou ville inconnue ⇒ prix catalogue de la ligne Transport.
    """

    company: object
    kwc: float = 0.0
    nb_panneaux: int = 0
    panel_watt: object = None
    scenario: str = COMPOSITION_SANS
    structure_type: str = 'acier'
    structure_produit_id: object = None
    taux_tva: Decimal = Decimal('20')
    mppt_paires: int = 1
    phase: object = None
    gamme_nom_devis: object = None
    dimensionnement_avec: object = None
    avertissements: object = None
    variante: str = ''
    hors_reseau: bool = False
    ville: str = ''
    #: QJR605 — BATHOMO : le calibre de module batterie DÉJÀ vendu par le
    #: devis (les sondes de taille). ``None`` (LE DÉFAUT) ⇒ choix économique.
    batterie_module_kwh: object = None
    #: QJR605 — ``ReglagesComposition`` DÉJÀ lus par ``reglages_de_composition``
    #: pour un appelant qui compose N fois (balayages). ``None`` (LE DÉFAUT)
    #: ⇒ lus ici, à chaque composition.
    reglages: object = None
    #: ACAL63 — les modèles DÉSIGNÉS par le calepinage (``[{produit_id, watt,
    #: count}]``). ``None`` (LE DÉFAUT) ⇒ un seul panneau, choisi au wattage.
    modeles: object = None


@dataclass(frozen=True)
class ReglagesComposition:
    """QJR605 — le catalogue et les règles de gamme d'une société, LUS UNE
    FOIS par :func:`reglages_de_composition` pour un balayage de N tailles."""

    catalogue: object
    marques: object
    ordre_lignes: object


def reglages_de_composition(company, gamme_nom_devis=None):
    """Les réglages que :func:`composer` lit — la MÊME lecture, factorisée."""
    return ReglagesComposition(
        catalogue=catalogue_de_la_societe(company),
        marques=carte_marques_composition(company, gamme_nom_devis),
        ordre_lignes=ordre_lignes_societe(company))


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
    # QJR-OFFGRID — un site ISOLÉ n'a qu'UNE composition possible (autonome +
    # stockage) : ni forme deux options, ni fusion L-2OPT, quel que soit le
    # scénario demandé par ailleurs.
    hors_reseau = bool(getattr(intention, 'hors_reseau', False))
    if hors_reseau:
        avec_batterie, deux_options = True, False

    avec = (intention.dimensionnement_avec
            if isinstance(intention.dimensionnement_avec, dict) else None)

    company = intention.company
    reglages = (getattr(intention, 'reglages', None)
                or reglages_de_composition(company, intention.gamme_nom_devis))
    commun = dict(
        panel_watt=intention.panel_watt,
        structure_type=intention.structure_type,
        # STKCAT7 — le produit de structure CHOISI suit les deux formes de
        # composition (mono-optimum et fusion L-2OPT) : un paramètre transmis
        # d'un côté et oublié de l'autre est exactement ce que QJR80 a corrigé.
        structure_produit_id=getattr(intention, 'structure_produit_id', None),
        taux_tva=intention.taux_tva,
        avertissements=intention.avertissements,
        # U3 — les règles de gamme vivent CÔTÉ SERVEUR et sont résolues ICI :
        # marques épinglées (PVMRQ) et ordre par défaut (PVORD).
        marques=reglages.marques,
        ordre_lignes=reglages.ordre_lignes,
        mppt_paires=intention.mppt_paires,
        phase=intention.phase,
    )
    catalogue = reglages.catalogue
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
            hors_reseau=hors_reseau,
            batterie_module_kwh=getattr(intention, 'batterie_module_kwh', None),
            modeles=getattr(intention, 'modeles', None),
            **commun)
    # QJR604 — LE BARÈME TRANSPORT est appliqué ICI, pour toutes les origines,
    # avant l'écriture des lignes (donc avant le cliché de marge et le gel du
    # prix/kWc). Ville inconnue ⇒ prix catalogue, aucun chiffre deviné.
    lignes = appliquer_bareme_transport(
        lignes, getattr(intention, 'ville', '') or '')
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


# ── QJR605 — LES SONDES DE TAILLE composent par le MÊME constructeur ─────────
# Les cartes Éco / Recommandé / Max (``offres_tailles``), l'échelle de paliers
# batterie (``domain/dimensionnement_devis``) et le balayage de tailles
# (``dimensionnement.balayer_tailles``) appelaient ``composition_residentielle``
# en direct : sans la gamme du devis, sans la phase, sans les paires MPPT,
# sans le hors-réseau — un autre kit que celui du devis. Ils construisent
# désormais leur intention ICI, et délèguent à :func:`composer`.


@dataclass(frozen=True)
class ContexteSonde:
    """Ce qu'une sonde de taille sait du devis (ou des entrées) qu'elle
    balaye. GELÉ ; ``reglages`` est lu UNE fois pour tout le balayage."""

    company: object
    reglages: object = None
    panel_watt: object = None
    gamme_nom_devis: object = None
    structure_type: str = 'acier'
    structure_produit_id: object = None
    phase: object = None
    mppt_paires: int = 1
    taux_tva: Decimal = Decimal('20')
    hors_reseau: bool = False
    ville: str = ''


def _mppt_paires_du_devis(devis):
    """Les paires MPPT que le devis chiffre : son câble DC AU MÈTRE ÷ 60 m
    (``metre_cable_dc_par_paires``, la règle de la composition). Sans ligne
    lisible : le repli fondateur d'une paire."""
    from apps.ventes.domain.catalogue import (
        CABLE_DC_M_PAR_PALIER, _est_au_metre, _is_cable_dc)
    metres = 0.0
    for ligne in devis.lignes.all():
        nom = ligne.designation or ''
        if _is_cable_dc(nom) and _est_au_metre(nom):
            metres += float(ligne.quantite or 0)
    if metres <= 0:
        return 1
    return max(1, int(round(metres / CABLE_DC_M_PAR_PALIER)))


def contexte_sonde_du_devis(devis, *, reglages=None):
    """Le ``ContexteSonde`` d'un devis : gamme, structure, phase, MPPT, TVA,
    hors-réseau et ville du barème — lus UNE fois, sur le devis et son lead."""
    from apps.crm.selectors import lead_du_devis
    from apps.ventes.domain.composition import structure_produit_id_du_devis
    from apps.ventes.domain.gammes import gamme_nom
    from apps.ventes.domain.taille import phase_et_isolement_du_lead
    lead = lead_du_devis(devis)
    # ACAL32 — phase et site isolé du lead lus par LE survivant
    # (``taille.phase_et_isolement_du_lead``) ; la détection par lignes
    # autonomes déjà posées reste propre au devis existant.
    phase, isole = phase_et_isolement_du_lead(lead)
    gamme = gamme_nom(devis) or None
    hors_reseau = isole or any(
        _is_offgrid_inverter(ligne.designation or '')
        and float(ligne.quantite or 0) > 0
        for ligne in devis.lignes.all())
    taux = getattr(devis, 'taux_tva', None)
    return ContexteSonde(
        company=devis.company,
        reglages=reglages or reglages_de_composition(devis.company, gamme),
        gamme_nom_devis=gamme,
        structure_produit_id=structure_produit_id_du_devis(devis),
        phase=phase,
        mppt_paires=_mppt_paires_du_devis(devis),
        taux_tva=Decimal(str(taux)) if taux is not None else Decimal('20'),
        hors_reseau=bool(hors_reseau),
        ville=ville_du_lead(lead))


def composer_sonde(contexte, nb_panneaux, *, avec_batterie, cible_kwh=None,
                   module_kwh=None, avertissements=None):
    """QJR605 — LA composition d'une taille sondée : l'intention du devis
    (``contexte``) à ``nb_panneaux``, mono-option, déléguée à :func:`composer`.
    """
    watt = float(contexte.panel_watt or _AUTO_PANEL_WATT)
    nb = int(nb_panneaux or 0)
    return composer(IntentionComposition(
        company=contexte.company,
        kwc=nb * watt / 1000.0,
        nb_panneaux=nb,
        panel_watt=watt,
        scenario=COMPOSITION_AVEC if avec_batterie else COMPOSITION_SANS,
        structure_type=contexte.structure_type,
        structure_produit_id=contexte.structure_produit_id,
        taux_tva=contexte.taux_tva,
        mppt_paires=contexte.mppt_paires,
        phase=contexte.phase,
        gamme_nom_devis=contexte.gamme_nom_devis,
        dimensionnement_avec=({'batterie_kwh': cible_kwh}
                              if (avec_batterie and cible_kwh) else None),
        avertissements=avertissements if avertissements is not None else [],
        hors_reseau=contexte.hors_reseau,
        ville=contexte.ville,
        batterie_module_kwh=module_kwh,
        reglages=contexte.reglages))


def sonder_wattage(contexte):
    """LA sonde de wattage : le Wc du panneau RÉELLEMENT retenu par le
    catalogue pour ce contexte (un panneau composé au wattage de référence),
    ou ``0``. Le hors-réseau n'y entre pas : le panneau retenu n'en dépend
    pas, et un catalogue sans onduleur autonome ne doit pas masquer le Wc."""
    sonde = composer_sonde(
        dataclasses.replace(contexte, panel_watt=_AUTO_PANEL_WATT,
                            hors_reseau=False), 1,
        avec_batterie=False)
    try:
        return float(getattr(sonde, 'panel_watt_reel', 0) or 0)
    except (TypeError, ValueError):
        return 0.0


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
#: QJR-OFFGRID — le message du site ISOLÉ. Il NOMME la référence manquante :
#: aucun repli sur un onduleur hybride n'est proposé ni fait, parce qu'un
#: hybride n'est pas une version dégradée d'un autonome — c'est un autre
#: produit, qu'un client sans raccordement ne peut pas exploiter (règle
#: fondateur : jamais un composant substitué en silence).
#: ROUND 2 (01/09/2026) — le message est ACTIONNABLE : il dit COMMENT la
#: reconnaissance marche (le NOM du produit, pas une catégorie à cocher),
#: parce que le premier incident venait justement d'un nom qui ne matchait
#: aucun mot-clé.
MSG_SANS_ONDULEUR_OFFGRID = (
    'Aucun onduleur hors réseau (off-grid) tarifé au catalogue. Le NOM du '
    'produit doit contenir « off-grid », « off grid », « hors réseau » ou '
    '« autonome » (ex. « Deye Off-Grid 6kW ») — et un prix de vente '
    'renseigné. Aucun onduleur hybride ne lui est substitué.')


def message_batterie_incompatible(plage):
    """PVOND — « aucune batterie » et « aucune batterie COMPATIBLE avec cet
    onduleur » n'appellent pas le même geste : on dit lequel."""
    return ('Aucune batterie compatible tarifée pour cet onduleur '
            '(plage %s-%s V). Ajoutez une batterie compatible tarifée, '
            'ou choisissez un autre onduleur, avant de générer ce '
            'devis.' % (_v_txt(plage[0]), _v_txt(plage[1])))


def refus_modeles_designes(company, modeles):
    """ACAL63 — les messages FRANÇAIS des modèles désignés NON servables :
    fiche introuvable dans le catalogue de la société, ou fiche non tarifée
    (« tarifez la fiche X »). ``[]`` quand tout est servable."""
    erreurs = []
    designes = [m for m in (modeles or ())
                if isinstance(m, dict) and m.get('produit_id')]
    if not designes or company is None:
        return erreurs
    par_pk = {getattr(p, 'pk', None): p
              for p in catalogue_de_la_societe(company)}
    for modele in designes:
        try:
            cle = int(modele['produit_id'])
        except (TypeError, ValueError):
            cle = None
        produit = par_pk.get(cle)
        if produit is None:
            erreurs.append(
                'Le module désigné par le calepinage (fiche produit #%s) est '
                'introuvable dans votre catalogue : choisissez un module de '
                'votre catalogue dans l\'atelier, puis relancez.'
                % modele['produit_id'])
        elif not _has_price(produit):
            erreurs.append(
                'Le module désigné par le calepinage n\'est pas tarifé : '
                'tarifez la fiche « %s » (prix de vente) puis relancez.'
                % (getattr(produit, 'nom', '') or '#%s' % cle))
    return erreurs


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
    # ACAL63 — un module DÉSIGNÉ par le calepinage doit être une fiche
    # TARIFÉE de la société : sinon refus NOMMÉ (défaut gravé), jamais un
    # repli sur le panneau le moins cher du même wattage.
    erreurs.extend(refus_modeles_designes(
        intention.company, getattr(intention, 'modeles', None)))

    scenario = (intention.scenario or '').strip().lower()
    company = intention.company

    # ── QJR-OFFGRID — LE SITE ISOLÉ A SA PROPRE LISTE D'EXIGENCES ───────────
    # Elle REMPLACE celle des trois scénarios raccordés (aucun onduleur réseau
    # ni hybride n'est attendu ici) : onduleur AUTONOME tarifé + batterie
    # COMPATIBLE de cet onduleur-là. Les deux manques sont NOMMÉS séparément —
    # le commercial doit savoir laquelle des deux références ajouter.
    if bool(getattr(intention, 'hors_reseau', False)):
        onduleur = _pick_product(company, _is_offgrid_inverter)
        batterie = _pick_batterie(company, onduleur=onduleur)
        if onduleur is None:
            erreurs.append(MSG_SANS_ONDULEUR_OFFGRID)
        if batterie is None:
            plage = _plage_batterie_de_l_onduleur(onduleur)
            if plage and plage[1] > 0:
                erreurs.append(message_batterie_incompatible(plage))
            else:
                erreurs.append(MSG_SANS_BATTERIE)
        return erreurs or None

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
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps — jamais
# ``pipeline`` (qui importe ce module) ni la façade.
from apps.ventes.domain.catalogue import (  # noqa: E402
    _has_price,
    _is_hybrid_inverter,
    _is_offgrid_inverter,
    _is_reseau_inverter,
    _pick_batterie,
    _pick_product,
    _plage_batterie_de_l_onduleur,
    carte_marques_composition,
    catalogue_de_la_societe,
    ordre_lignes_societe,
)
from apps.ventes.domain.composition import (  # noqa: E402
    CompositionLignes,
    _v_txt,
    composition_deux_optimiseurs,
    composition_residentielle,
)
from apps.ventes.domain.taille import _AUTO_PANEL_WATT  # noqa: E402
from apps.ventes.domain.transport import (  # noqa: E402
    appliquer_bareme_transport,
    ville_du_lead,
)
