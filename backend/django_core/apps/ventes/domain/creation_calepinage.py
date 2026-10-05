"""Le pont calepinage → devis (SPL266, déplacé de ``domain/creation.py``).

Le devis composé depuis un layout 3D (``build_devis_from_layout``, adaptateur
de ``pipeline.appliquer`` — origine calepinage), l'arbitrage du compte retenu
(``_arbitrage_du_calepinage``), le calepinage rangé dans l'étude
(``_calepinage_range``) et le devis depuis le calepinage RETENU (CAL185 :
``build_devis_depuis_calepinage_retenu``, ``produits_a_renseigner``). Le
module construit un Devis : propriété devis ; le calepinage garde la lecture du
layout (``domain/geometrie``).

ORDRE DE CHARGEMENT : les noms lus ailleurs dans ``domain/`` sont importés EN
BAS de ce fichier, en visant le module qui porte le corps (``creation`` pour
``_structure_demandee``, qui n'importe jamais ce module) — jamais la façade.
Déplacement pur : corps octet-identiques, prouvé par
``tests/golden/split_dm_cal.json``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal
import logging

logger = logging.getLogger("apps.ventes.services")


def _arbitrage_du_calepinage(layout, nb_panneaux, kwc, *, company):
    """AOF164 / PVG2 — le compte RETENU pour ce layout, et le kWc qui le SUIT.

    UNE SEULE écriture de cette règle, pour les DEUX chemins de création qui la
    subissent (le calepinage 3D et le devis automatique, QJR96) : la recopier
    aurait suffi à ce que la bascule A/B du moteur de calepinage s'applique d'un
    côté et pas de l'autre — c'est-à-dire à ce que le même toit sorte avec deux
    comptes de modules selon le bouton par lequel le devis est né.

    Drapeau ``USE_MOTEUR_CALEPINAGE`` baissé (le défaut) ⇒ ``arbitrer_compte_
    calepinage`` rend ``None`` AVANT tout calcul et ce couple ressort tel quel :
    comportement bit-identique à l'historique. Au-delà de la tolérance PVG2,
    ``retenu`` REDEVIENT le compte historique et rien ne bouge non plus.

    Le kWc SUIT le compte : laisser l'ancien kWc face au nouveau compte
    produirait un devis dont la puissance ne correspond plus aux panneaux.

    QJR243 (c) — LE WATTAGE PASSE PAR LE LECTEUR UNIQUE. Cette fonction
    re-parsait ``panelWatt`` EN LIGNE, sans la normalisation ni la garde
    d'exception de ``geometrie.lire_layout`` (QJR165) : un blob portant
    ``"abc"`` faisait LEVER la création de devis (``float("abc")``), et un
    ``545.6`` produisait un kWc calculé sur un wattage que le reste du dépôt
    aurait arrondi. Le lecteur est appelé AVANT la réaffectation du compte,
    donc sur le couple (compte, kWc) d'ORIGINE : la déduction de repli garde
    exactement la même base qu'avant. ``watt_declare`` (et non ``watt``) parce
    qu'un wattage INCONNU doit laisser le kWc tel quel, jamais le recalculer
    sur le défaut catalogue.
    """
    arbitrage = arbitrer_compte_calepinage(layout, nb_panneaux,
                                           company=company)
    if arbitrage is None or arbitrage['retenu'] == nb_panneaux:
        return nb_panneaux, kwc
    watt_reference = lire_layout(
        layout, compte=nb_panneaux, kwc=kwc).watt_declare
    nb_panneaux = arbitrage['retenu']
    if watt_reference:
        kwc = round(nb_panneaux * float(watt_reference) / 1000.0, 3)
    return nb_panneaux, kwc


def _calepinage_range(layout, toiture, kwc):
    """QJ21 / FG248 — ce qu'un calepinage APPORTE au devis, lu UNE fois.

    Rend ``(layout_stocke, etude_initiale)`` :

    * ``layout_stocke`` est une COPIE du layout de l'appelant (on ne mute jamais
      son dict) enrichie de ``_pans_geometry``, la géométrie par pan DÉJÀ
      PROCESSÉE, pour qu'aucun consommateur n'ait à rejouer
      ``extract_roof_config`` ;
    * ``etude_initiale`` est l'étude que ce chemin APPORTE, et lui seul : le kWc
      que le TOIT modélise et la configuration de toiture importée du builder
      3D. Le pipeline la transporte jusqu'à la création ; il n'en dérive rien.
      Le kWc, lui, est RE-POSÉ ensuite par son propriétaire sur les lignes
      réellement écrites (QJR63, étape 8) — le calepinage modélise à 720 W
      constants quand le devis vend le panneau RÉEL (710 W sur
      DEV-202608-0007), et stocker les deux mettrait deux bases de puissance
      dans le même document.

    QJR96 — LES DEUX ADAPTATEURS DE CRÉATION LISENT ICI. Le devis automatique
    synthétise lui aussi un layout (le tracé du client devient une vraie zone
    roofPro11, ``zone_toit_depuis_contour``) : sans ce lecteur commun, un devis
    né du tunnel repartait sans ``_pans_geometry`` ni ``etude_params['toiture']``
    dès qu'il cessait de passer par ``build_devis_from_layout``.
    """
    layout_stocke = dict(layout or {})
    if toiture and toiture.get('pans'):
        layout_stocke['_pans_geometry'] = toiture['pans']
    etude_initiale = {}
    if kwc:
        etude_initiale['puissance_kwc'] = kwc
    if toiture:
        etude_initiale['toiture'] = toiture
    return layout_stocke, etude_initiale


def build_devis_from_layout(*, layout, user, company, lead=None, client=None,
                            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
                            deux_options=False, journal=None, phase=None,
                            dimensionnement_avec=None,
                            mppt_paires=1, structure_type=None,
                            structure_produit_id=None, hors_reseau=None):
    """Q3 — turn a FINALISED roof layout into a coherent, company-scoped Devis.

    ``mppt_paires`` / ``structure_type`` (QJR80) — les DEUX paramètres de
    composition que cette fonction n'acceptait pas et ne transmettait donc
    jamais, pendant que le dry-run qui l'approuve
    (``composer_devis_residentiel``) les transmettait : l'aperçu et le devis
    pouvaient diverger sur les mètres de câble DC et sur le matériau de
    structure. Les défauts sont ceux de ``composition_residentielle``
    (1 paire, acier), donc un appelant qui ne les renseigne pas compose
    EXACTEMENT ce que ce dépôt composait déjà.

    ``deux_options`` (U2, fondateur 20/08/2026) — compose la forme DEUX
    OPTIONS (« sans batterie » ET « avec batterie » dans un seul devis, cf.
    ``composition_residentielle``) et stocke le scénario correspondant. Défaut
    False : le calepinage 3D a DÉJÀ arrêté son scénario à l'écran, il garde
    donc sa composition mono-option, byte-identique à l'historique.

    ``dimensionnement_avec`` (L-2OPT, optionnel) — ce que le moteur calibré
    recommande POUR L'OPTION AVEC BATTERIE, quand ce n'est pas le même champ PV
    que l'option sans : ``{'nb_panneaux': int, 'kwc': float,
    'batterie_kwh': float | None}``. Combiné à ``deux_options``, il fait
    composer DEUX kits complets, fusionnés en lignes VARIANTÉES (cf.
    :func:`composition_deux_optimiseurs`). ``None`` (LE DÉFAUT) ⇒ un seul champ
    PV, exactement comme aujourd'hui — et un ``nb_panneaux`` identique à celui
    de l'option sans y retombe aussi, par le repli de sécurité de la fusion.

    ``journal`` (U3, optionnel) — dict que l'appelant fournit et que la
    construction remplit sur place avec ce que la composition a REFUSÉ de
    faire : ``marques_manquantes`` (rôles épinglés sans AUCUN candidat en
    stock) et ``avertissements`` (vivier batterie vide…). Sans ce canal, un
    devis pouvait partir SANS panneaux — la marque épinglée ayant vidé leur
    vivier — à un prix effondré, sans que personne ne l'apprenne. Absent
    (``None``) ⇒ comportement inchangé.

    ``phase`` (PVCOMPAT, optionnel) — le RACCORDEMENT déclaré par le client
    (``'monophase'``/``'triphase'``), transmis tel quel à
    ``composition_residentielle`` : un abonnement monophasé n'accepte pas un
    onduleur triphasé. ``None`` ⇒ ACAL32 : déduit du LEAD
    (``taille.phase_et_isolement_du_lead``) ; sans lead, aucun filtre.

    ``hors_reseau`` (ACAL32, C-ACAL-105) — le site est ISOLÉ. ``None`` ⇒
    déduit du lead (``raccordement='aucun'``), comme le devis automatique :
    onduleur AUTONOME + batterie en option unique, et un catalogue incapable
    de les servir lève ``AutoDevisError(field='hors_reseau')`` (→ 422 nommé)
    AVANT toute écriture — jamais un onduleur réseau, jamais un 500.

    ``layout`` is the serialized roofPro11 output (see Devis.roof_layout):
    a ``result`` block ``{panels, kwc, annualKwh, savings}`` plus an optional
    ``scenario``/equipment hint. From it we compose Devis lines off the seeded
    catalogue via ``composition_residentielle`` — le KIT COMPLET du simulateur
    (panneau, onduleur du bon palier, batteries, structures, socles,
    accessoires, tableau de protection AC/DC, installation, transport, et le
    duo Smart Meter + clé Wifi derrière un onduleur Huawei), et non plus le seul
    squelette panneau + onduleur. La classification par mots-clés reste celle du
    moteur PDF (panneau / onduleur réseau|injection|hybride / batterie) et la
    référence passe toujours par l'util anti-collision (jamais count()+1). The
    client is resolved server-side from the lead via crm.services (no
    duplicates). The layout's production/savings are stored into
    ``etude_params``. A price-less catalogue product is NEVER quoted, and a
    component missing from the catalogue is skipped rather than fatal.

    QJ21 — the stored ``roof_layout`` is enriched with a ``_pans_geometry`` key
    holding the processed per-pan list (azimut_deg, inclinaison_deg, kwc,
    nb_panneaux, orientation, label, roof_type) so consumers never have to
    re-run ``extract_roof_config`` to access the full multi-plane design.

    Returns the created Devis. The Devis is left ``brouillon`` — this service
    only BUILDS; it never changes downstream statuses (rule #4).

    QJR95 (M5, bascule 3/5) — CETTE FONCTION EST DEVENUE UN ADAPTATEUR. Ce
    qu'elle garde est la LECTURE DU CALEPINAGE : d'un layout 3D tirer un compte
    de panneaux, un wattage, un kWc, un scénario et une toiture. C'est la seule
    chose que ce chemin sait faire et que les quatre autres ne savent pas, donc
    la seule qui reste ici. Tout ce qui suivait — composer, vérifier, créer,
    écrire les lignes, écrire l'étude, finaliser — était une recopie des mêmes
    étapes dans un ordre qui n'était celui d'aucun autre chemin ; elle est
    SUPPRIMÉE et remplacée par un appel à ``pipeline.appliquer``.

    DEUX GAINS ASSUMÉS (R4-C.5, portés au DONE LOG) :

    * les QUATRE ÉTUDES sont désormais rafraîchies. Ce chemin n'appelait
      ``rafraichir_etudes_du_devis`` **pas du tout** : un devis né du calepinage
      partait sans bloc horaire, sans tableau de dimensionnement et sans profils
      comparatifs, et n'en recevait qu'au premier enregistrement ultérieur ;
    * la PRÉ-VÉRIFICATION passe aux trois scénarios (QJR82). Elle n'existait ici
      que dans la vue appelante, en version mono-scénario : un devis à deux
      options pouvait naître avec un seul onduleur composable, et ne servir
      qu'une des deux options qu'il promet au client.
    """
    # STKCAT8/STKCAT9 (bis) — le chemin 3D suit la MÊME règle que /auto/ :
    # le choix imposé par l'appelant d'abord, sinon la structure épinglée
    # sur le lead, sinon sa préférence acier/aluminium, sinon acier (le
    # défaut historique — un appelant qui passe 'acier' compose comme hier).
    structure_produit_id, structure_type = _structure_demandee(
        lead, structure_produit_id, structure_type)
    from apps.ventes.models import Devis
    from apps.ventes.utils.options import deux_options_composables

    # ── ACAL32 (C-ACAL-105) — LA PHASE ET LE SITE ISOLÉ DU LEAD ────────────
    # Déduits UNE fois ici (le module calepinage ET from-layout passent par
    # ce point) quand l'appelant ne les fournit pas : un lead triphasé ne
    # reçoit plus un onduleur monophasé, un site isolé jamais un onduleur
    # réseau.
    phase_lead, isole_lead = phase_et_isolement_du_lead(lead)
    if phase is None:
        phase = phase_lead
    hors_reseau = isole_lead if hors_reseau is None else bool(hors_reseau)
    deux_options = deux_options_composables(deux_options, hors_reseau)

    if client is None:
        if lead is None:
            raise ValueError("build_devis_from_layout requires a lead or client")
        from apps.crm.services import resolve_client_for_lead
        client = resolve_client_for_lead(lead)

    # ── QJR165 — LE LECTEUR UNIQUE DU LAYOUT ───────────────────────────────
    # Ce chemin lisait le layout INLINE (compte, kWc, wattage, batterie)
    # pendant que la resynchronisation le lisait par ``geometrie.lire_layout``.
    # Les deux chaînes de repli avaient réellement divergé — ``result.count``
    # accepté d'un seul côté, le forfait 550 W posé d'un seul côté, le wattage
    # normalisé d'un seul côté, le scénario « les deux » compris d'un seul
    # côté : le même toit pouvait ressortir avec deux comptes ou deux wattages
    # selon le bouton. La lecture inline est SUPPRIMÉE ; la chaîne tranchée
    # vit dans ``lire_layout``, et ``toiture`` (FG248, le pont 3D → ERP) en
    # revient avec le reste au lieu d'être re-extraite ici.
    #
    # QJR95 — ``annualKwh`` / ``savings`` ne sont pas relus ICI : la production
    # et les économies que le calepinage porte sont écrites par l'étape 6
    # (``pipeline.ecrire_etude_params``), qui les lit dans le MÊME bloc
    # ``result`` du layout transmis. Les relire des deux côtés, c'était deux
    # lecteurs pour une donnée.
    lecture = lire_layout(layout)
    toiture = lecture.toiture

    # AOF164 / PVG2 — la bascule A/B du moteur de calepinage, écrite une seule
    # fois pour les deux chemins de création (cf. ``_arbitrage_du_calepinage``).
    nb_panneaux, kwc = _arbitrage_du_calepinage(
        layout, lecture.compte, lecture.kwc, company=company)
    if (nb_panneaux, kwc) != (lecture.compte, lecture.kwc):
        # Le couple ARBITRÉ devient la base de lecture : le wattage se déduit
        # du compte RETENU, jamais de celui que l'arbitrage vient d'écarter.
        # Drapeau moteur baissé (le défaut) ⇒ l'arbitrage est l'identité et
        # cette relecture n'a pas lieu.
        lecture = lire_layout(layout, toiture=toiture,
                              compte=nb_panneaux, kwc=kwc)
    watt = lecture.watt

    # PVKIT — le KIT COMPLET du simulateur (structures, socles, accessoires,
    # tableau de protection, installation, transport…), plus le squelette
    # panneau + onduleur ± batterie d'hier : voir ``composition_residentielle``.
    # Un composant absent (ou non tarifé) du catalogue est simplement sauté.
    from apps.ventes.domain.lignes import LAYOUT_WATT_REPLI
    kwc_composition = kwc or (
        nb_panneaux * float(watt or LAYOUT_WATT_REPLI) / 1000.0)

    # QJ21 / FG248 — le layout RANGÉ (avec sa géométrie par pan déjà processée)
    # et l'étude que ce chemin APPORTE, par LE MÊME lecteur que le devis
    # automatique (cf. ``_calepinage_range``).
    stored_layout, etude_initiale = _calepinage_range(layout, toiture, kwc)

    # ACAL32 — un site ISOLÉ n'a qu'une composition : autonome + batterie,
    # mono-option. Le catalogue qui ne la sert pas est un REFUS NOMMÉ
    # (``hors_reseau``), prononcé AVANT toute écriture — comme le devis
    # automatique (``creation_auto``).
    scenario = (COMPOSITION_LES_DEUX if deux_options else lecture.scenario)
    if hors_reseau:
        scenario = COMPOSITION_AVEC
        refus_isole = verifier(IntentionComposition(
            company=company, nb_panneaux=nb_panneaux, kwc=kwc_composition,
            scenario=COMPOSITION_AVEC, phase=phase, hors_reseau=True))
        if refus_isole and refus_isole[0] != MSG_AUCUN_PANNEAU:
            raise AutoDevisError(refus_isole[0], field='hors_reseau')

    # ── QJR95 — LE PIPELINE, DANS SON ORDRE UNIQUE ─────────────────────────
    # La cible est SOUVERAINE : elle vient du toit que le commercial a dessiné,
    # et l'étape 2 ne redimensionne donc rien. Le scénario du layout est dit
    # dans le SEUL vocabulaire du pipeline — ``deux_options`` l'emporte, comme
    # le faisait déjà la composition (où ``avec_batterie`` n'a aucun effet dès
    # que la forme est à deux options). PVCOMPAT (``phase``), QJR80
    # (``mppt_paires`` / ``structure_type``) et L-2OPT (``dimensionnement_avec``)
    # sont transmis par les mêmes champs que les quatre autres origines.
    resultat = appliquer(None, IntentionDevis(
        origine=ORIGINE_CALEPINAGE,
        company=company,
        user=user,
        lead=lead,
        client=client,
        mode_installation=Devis.ModeInstallation.RESIDENTIEL,
        cible=CibleDevis(
            nb_panneaux=nb_panneaux,
            panel_watt=watt,
            kwc=kwc_composition,
            source='calepinage',
            dimensionnement_avec=dimensionnement_avec),
        # QJR165 — le scénario vient du MÊME lecteur que la pré-vérification
        # qui précède cette création (``validate_composition_for_layout`` lit
        # déjà ``scenario_du_layout``). Le couple ``batterie``/``hybride`` +
        # la clé ``battery`` est lu à l'identique ; c'est le libellé
        # « les deux » que la lecture inline ne savait pas comprendre — elle
        # composait alors une option SANS un devis que le pré-vol venait de
        # vérifier sur DEUX. ``deux_options`` reste souverain quand
        # l'appelant le demande explicitement.
        scenario=scenario,
        layout=stored_layout,
        etude_initiale=etude_initiale or None,
        taux_tva=taux_tva,
        remise_globale=remise_globale,
        structure_type=structure_type,
        # STKCAT7 — le produit de structure CHOISI traverse la création comme
        # il traverse le dry-run : les deux remplissent la MÊME intention.
        structure_produit_id=structure_produit_id,
        mppt_paires=mppt_paires,
        phase=phase,
        hors_reseau=hors_reseau,
    ))
    devis = resultat['devis']
    line_specs = resultat['composition']
    avertissements = resultat['avertissements']

    # U3 — le canal de l'appelant, rempli sur place comme avant. Il porte en
    # plus, désormais, ce que l'ÉCRIVAIN de lignes a refusé de faire (QJR83,
    # forfaits au panneau) : la composition n'était que la moitié des choses
    # qu'un commercial doit apprendre.
    if journal is not None:
        journal['marques_manquantes'] = list(
            getattr(line_specs, 'marques_manquantes', ()) or ())
        journal['avertissements'] = list(avertissements or ())
        journal['nb_panneaux'] = getattr(line_specs, 'nb_panneaux', 0)
        journal['kwc_reel'] = getattr(line_specs, 'kwc_reel', 0.0)
    elif avertissements:
        # Sans canal fourni, la composition journalisait elle-même ses refus.
        # Le pipeline, lui, les COLLECTE toujours : on les journalise ici
        # plutôt que de les laisser dans une liste que personne ne lit.
        for message in avertissements:
            logger.warning('Q3: devis depuis layout — %s', message)

    logger.info(
        'Q3/QJ21: devis %s built from layout (%d lignes, %.2f kWc, %d pans, company %s)',
        devis.reference, len(line_specs or ()), kwc,
        len(toiture.get('pans', [])) if toiture else 0,
        getattr(company, 'id', '?'))
    return devis


#: CAL185 — les familles du KIT, c'est-à-dire les catégories que la
#: composition sait servir toute seule (``classer_produit``). Un produit
#: hors de ces familles (un accessoire choisi à la main, un service) n'a
#: aucune raison d'apparaître dans la liste « à renseigner » : personne
#: n'attendait qu'il soit chiffré automatiquement.
FAMILLES_KIT_CAL185 = ('panneau', 'batterie', 'onduleur_hybride',
                       'onduleur_reseau', 'onduleur_offgrid')


def produits_a_renseigner(company):
    """CAL185 — les produits du KIT que le catalogue ne peut PAS chiffrer.

    La composition écarte silencieusement tout produit sans prix de vente
    (garde ``_has_price``, la même que l'auto-remplissage pompage : « jamais
    un produit sans prix »). Ce silence est le défaut : un vivier dont TOUS
    les candidats sont dépourvus de prix fait simplement disparaître un
    composant du kit, sans que personne l'apprenne.

    Cette fonction NE CHOISIT RIEN et ne chiffre rien : elle LIT le catalogue
    déjà borné société (``catalogue_de_la_societe``) et le classe avec
    ``classer_produit`` — la classification de la composition, pas une
    seconde. Rendu : un objet léger par produit
    (``{produit, designation, famille}``), jamais le modèle ``Produit``, et
    JAMAIS le moindre montant (un produit listé ici n'a précisément pas de
    prix de vente ; ``prix_achat`` n'est lu par aucun chemin).
    """
    lignes = []
    for produit in catalogue_de_la_societe(company):
        famille = classer_produit(produit.nom)
        if famille in FAMILLES_KIT_CAL185 and not _has_price(produit):
            lignes.append({'produit': produit.pk,
                           'designation': produit.nom,
                           'famille': famille})
    return lignes


def build_devis_depuis_calepinage_retenu(*, calepinage_id, user, company,
                                         lead=None, client=None, **options):
    """CAL185 — chiffrer la VARIANTE RETENUE d'un calepinage, sans second chemin.

    ``from-layout`` savait déjà transformer une conception en lignes de devis,
    mais rien ne partait d'une variante RETENUE : le commercial comparait ses
    options dans le calepinage, en choisissait une… et devait la rechiffrer
    ailleurs. Cette fonction est le chaînon, et elle n'écrit AUCUNE ligne
    elle-même : elle lit la conception retenue par
    ``apps.calepinage.selectors.nomenclature_variante_retenue`` (jamais
    ``apps.calepinage.models``) et la passe à ``build_devis_from_layout``,
    LE chemin de création de lignes. Chaque ligne pointe donc un
    ``stock.Produit`` réel, et un produit sans prix de vente n'est jamais
    chiffré — la garde existante, pas une nouvelle.

    Ce qui est AJOUTÉ : ce que cette garde taisait. Le rapport rendu liste
    les produits du kit « à renseigner » (sans prix de vente), à côté des
    canaux existants (``avertissements``, ``marques_manquantes``).

    ``options`` est passé TEL QUEL à ``build_devis_from_layout`` (taux_tva,
    remise_globale, deux_options, structure_type…) : aucun défaut n'est
    réinventé ici.

    Returns:
        ``(devis, rapport)`` — ``rapport`` porte ``calepinage``, ``variante``,
        ``nom``, ``layout_hash``, ``a_renseigner``, ``avertissements`` et
        ``marques_manquantes``.

    Raises:
        ValueError: aucune variante retenue, ou variante sans conception —
            le message NOMME le geste manquant plutôt que de chiffrer autre
            chose (jamais un repli silencieux sur la conception parente).
    """
    from apps.calepinage.selectors import nomenclature_variante_retenue

    nomenclature = nomenclature_variante_retenue(calepinage_id, company)
    if nomenclature is None:
        raise ValueError(
            "Aucune variante retenue à chiffrer sur ce calepinage : "
            "comparez vos options, retenez-en une, puis relancez.")

    journal = {}
    devis = build_devis_from_layout(
        layout=nomenclature['layout'], user=user, company=company,
        lead=lead, client=client, journal=journal, **options)
    # Le devis porte l'empreinte de la VARIANTE : c'est ce qui rend le badge
    # « à jour » honnête (la fiche devis le compare à celle du calepinage).
    if nomenclature['layout_hash']:
        poser_layout_hash(devis, nomenclature['layout_hash'])
    rapport = {
        'calepinage': nomenclature['calepinage'],
        'variante': nomenclature['variante'],
        'nom': nomenclature['nom'],
        'layout_hash': nomenclature['layout_hash'],
        'a_renseigner': produits_a_renseigner(company),
        'avertissements': list(journal.get('avertissements') or ()),
        'marques_manquantes': list(journal.get('marques_manquantes') or ()),
    }
    return devis, rapport


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.catalogue import (  # noqa: E402
    _has_price,
    catalogue_de_la_societe,
    classer_produit,
)
from apps.ventes.domain.geometrie import (  # noqa: E402
    arbitrer_compte_calepinage,
    lire_layout,
    poser_layout_hash,
)
from apps.ventes.domain.pipeline import (  # noqa: E402
    ORIGINE_CALEPINAGE,
    CibleDevis,
    IntentionDevis,
    appliquer,
)
from apps.ventes.domain.etape_composer import (  # noqa: E402
    COMPOSITION_AVEC,
    COMPOSITION_LES_DEUX,
    MSG_AUCUN_PANNEAU,
    IntentionComposition,
    verifier,
)
from apps.ventes.domain.taille import (  # noqa: E402
    AutoDevisError,
    phase_et_isolement_du_lead,
)
# ``_structure_demandee`` reste dans ``creation`` (aussi lu par le devis
# automatique) ; ``creation`` ne lit ce module que pour le devis automatique.
from apps.ventes.domain.creation import _structure_demandee  # noqa: E402
