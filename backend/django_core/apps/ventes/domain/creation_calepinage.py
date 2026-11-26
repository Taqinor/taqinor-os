"""Le pont calepinage → devis (SPL266, déplacé de ``domain/creation.py``).

Le devis composé depuis un layout 3D (``build_devis_from_layout``, adaptateur
de ``pipeline.appliquer`` — origine calepinage), l'arbitrage du compte retenu
(``_arbitrage_du_calepinage``), le calepinage rangé dans l'étude
(``_calepinage_range``) et ``produits_a_renseigner`` (CAL185 ; le devis
depuis le calepinage RETENU est retiré par ACAL108 : un calepinage se chiffre
par SON « Générer le devis »). Le
module construit un Devis : propriété devis ; le calepinage garde la lecture du
layout (``domain/geometrie``).

ORDRE DE CHARGEMENT : les noms lus ailleurs dans ``domain/`` sont importés EN
BAS de ce fichier, en visant le module qui porte le corps (``creation`` pour
``_structure_demandee``, qui n'importe jamais ce module) — jamais la façade.
Déplacement pur : corps octet-identiques, prouvé par
``tests/golden/split_dm_cal.json``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from dataclasses import replace
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


#: ACON40 (ACAL89) — un lead AGRICOLE se chiffre depuis l'écran devis
#: agricole (pompage), jamais depuis un calepinage toiture.
MESSAGE_LEAD_AGRICOLE = ("Lead agricole : le pompage se chiffre depuis l'écran "
                         "devis agricole.")


def _marche_du_lead(lead):
    """ACON40 (D-ACON-1) — le marché du devis = ``lead.type_installation``
    s'il est un ``Devis.ModeInstallation``, sinon résidentiel ; agricole :
    refus nommé AVANT toute écriture."""
    from apps.ventes.models import Devis

    marche = (getattr(lead, 'type_installation', '') or '').lower()
    if marche == Devis.ModeInstallation.AGRICOLE:
        raise AutoDevisError(MESSAGE_LEAD_AGRICOLE, field='type_installation')
    return (marche if marche in Devis.ModeInstallation.values
            else Devis.ModeInstallation.RESIDENTIEL)


def composer_a_blanc_depuis_layout(*, layout, company, lead=None, onduleur_designe=None, journal=None):
    """Lane E9b — LE dry-run de « Générer le devis » (``build_devis_from_layout(a_blanc=True)``)
    sous ``conception.moteur.reglages_lus_sans_creer`` : la TVA et le tarif de la société sont
    lus sur la ligne existante, sinon sur une instance NON enregistrée — un ``GET`` ne crée
    jamais de ``CompanyProfile`` / ``TariffSettings``. Rend les specs de lignes.

    D-ACAL-148 — ``onduleur_designe`` / ``journal`` : ceux de la génération (même décision,
    rangée dans ``journal['onduleur_designe']``)."""
    from apps.ventes.conception.moteur import reglages_lus_sans_creer

    with reglages_lus_sans_creer(company):
        return build_devis_from_layout(layout=layout, user=None, company=company, lead=lead, a_blanc=True,
                                       onduleur_designe=onduleur_designe, journal=journal)


# ── D-ACAL-148 — L'ONDULEUR DÉSIGNÉ À L'ÉTAPE ÉLECTRIQUE ─────────────────────
#: Les trois familles d'onduleur qu'une composition résidentielle sait vendre.
FAMILLES_ONDULEUR_DESIGNABLES = ('onduleur_reseau', 'onduleur_hybride', 'onduleur_offgrid')
#: La suite de toute phrase de repli : ce que le devis fait à la place.
SUITE_REPLI_ONDULEUR = 'le devis garde l’onduleur de la conception du lead'
MESSAGE_ONDULEUR_NON_CHIFFRE = ('L’onduleur désigné à l’étape Électrique (« %s ») n’est pas chiffré : %s ; '
                                + SUITE_REPLI_ONDULEUR + '.')
MOTIFS_REPLI_ONDULEUR = {
    'introuvable': 'il n’est pas au catalogue de vente de la société (inconnu ou archivé)',
    'sans_prix': 'il n’a pas de prix de vente au catalogue',
    'pompage': 'c’est un article de pompage',
    'non_onduleur': ('il n’est reconnu comme onduleur réseau, hybride ou hors réseau ni par son rôle, '
                     'ni par sa fiche, ni par son nom'),
    'site_isole': 'le site est hors réseau : seul un onduleur hors réseau (autonome) peut être chiffré',
    'autonome_raccorde': 'c’est un onduleur hors réseau et le site est raccordé au réseau',
    'reseau_avec_batterie': 'c’est un onduleur réseau : il ne porte pas la batterie de ce devis',
    'hybride_sans_batterie': ('c’est un onduleur hybride et la pose est sans batterie : un hybride sans '
                              'batterie n’est pas chiffré automatiquement'),
    'batterie_non_composee': ('la règle de composition du devis ne pose aucune batterie avec lui (en stock, '
                              'tarifée, compatible)'),
    'nom_muet': ('son nom ne dit pas qu’il s’agit d’un onduleur %s : le PDF du devis et la '
                 'resynchronisation reconnaissent un onduleur à son nom'),
    'mono_sur_tri': ('il est monophasé et le raccordement du client est triphasé (le devis ne cote jamais '
                     'un monophasé à un client triphasé)'),
    'tri_sur_mono': 'il est triphasé et le raccordement du client est monophasé',
    'nombre_illisible': 'le nombre d’onduleurs saisi à l’étape Électrique n’est pas un entier d’au moins 1',
    'nombre_inconnu': ('le nombre d’onduleurs n’est ni accepté à l’étape Électrique ni établi par le schéma '
                       'du calepinage'),
}


def famille_onduleur_du_produit(produit, specs=None):
    """D-ACAL-148 — la famille de devis d'un onduleur (``FAMILLES_ONDULEUR_DESIGNABLES``) ou
    ``None``. Règle du fondateur du 24/11 (« un produit se reconnaît à son rôle et à sa fiche
    avant son nom ») : le rôle DÉCLARÉ, puis la fiche (port batterie publié ⇒ hybride,
    ``core.electrique.onduleurs.est_onduleur_hybride`` — la règle du calepinage), puis le nom
    (``catalogue.classer_produit``). Un micro-onduleur, ou un produit déclaré d'un autre rôle,
    n'est pas un onduleur du système. Fonction PURE (``specs`` : la fiche déjà lue)."""
    from core.electrique.onduleurs import est_onduleur_hybride
    from core.product_roles import role_declare

    from apps.ventes.selectors_calepinage import autre_famille_d_onduleur_par_nom

    if produit is None:
        return None
    nom = getattr(produit, 'nom', '') or ''
    role = role_declare(getattr(produit, 'role_devis', None))
    if role:
        return role if role in FAMILLES_ONDULEUR_DESIGNABLES else None
    autre = autre_famille_d_onduleur_par_nom(nom)
    if autre == 'micro_onduleur':
        return None
    fiche = specs or {}
    if est_onduleur_hybride(nom, ports_batterie_kw=(fiche.get('bat_max_charge_kw'),
                                                    fiche.get('bat_max_decharge_kw')),
                            autre_famille_par_nom=autre):
        return 'onduleur_hybride'
    par_nom = classer_produit(nom)
    return par_nom if par_nom in FAMILLES_ONDULEUR_DESIGNABLES else None


#: Le mot de chaque famille dans la phrase « son nom ne dit pas… ».
LIBELLE_FAMILLE_ONDULEUR = {'onduleur_reseau': 'réseau', 'onduleur_hybride': 'hybride',
                            'onduleur_offgrid': 'hors réseau'}


def famille_lue_au_nom(nom):
    """Relecture D-ACAL-148, point 2 — la famille d'onduleur que les LECTEURS AVAL d'une ligne
    voient : ``quote_engine/builder.py`` (paniers d'options, ``_has_qty(…, _is_hybrid_inverter)``
    sur ``utils.options.texte_classement``) et ``domain/lignes.py::_classe_ligne`` (resynchronisation)
    classent par le NOM seul, avec ces mêmes prédicats (``solar_classification``, réexportés par
    ``catalogue``). La désignation d'une ligne composée EST le nom du produit. Fonction PURE."""
    from apps.ventes.domain.catalogue import (
        _is_hybrid_inverter, _is_offgrid_inverter, _is_reseau_inverter)
    from apps.ventes.utils.options import texte_classement

    texte = texte_classement(nom or '', nom or '')
    for famille, predicat in (('onduleur_hybride', _is_hybrid_inverter),
                              ('onduleur_offgrid', _is_offgrid_inverter),
                              ('onduleur_reseau', _is_reseau_inverter)):
        if predicat(texte):
            return famille
    return None


def repli_onduleur_designe(nom, motif, famille=None):
    """La décision de REPLI (la composition d'aujourd'hui) et sa phrase. Fonction PURE."""
    texte = MOTIFS_REPLI_ONDULEUR[motif]
    if motif == 'nom_muet':
        texte = texte % LIBELLE_FAMILLE_ONDULEUR[famille]
    return {'impose': None, 'option': None, 'nom': nom, 'batterie_a_verifier': False,
            'motif': '%s ; %s' % (texte, SUITE_REPLI_ONDULEUR),
            'message': MESSAGE_ONDULEUR_NON_CHIFFRE % (nom, texte)}


def decision_onduleur_designe(*, produit_id, nom, etat, famille, famille_au_nom, scenario, hors_reseau,
                              nombre=None, nombre_illisible=False, phase_client=None, triphase=None):
    """D-ACAL-148 — que fait le devis de l'onduleur DÉSIGNÉ ? Fonction PURE.

    ``etat`` : ``'tarife'`` (au catalogue, avec un prix de vente) ou la clé du motif de repli
    (``'introuvable'``, ``'sans_prix'``, ``'pompage'``). Rend ``{impose, option, motif, message}`` :

    * ``impose`` — ``{'produit_id', 'categorie', 'nombre'}`` transmis à la composition
      (``CibleDevis.onduleur_impose``), ou ``None`` (repli : la composition d'aujourd'hui) ;
    * ``option`` — l'option qui le porte : ``''`` (devis à une option), ``'sans'`` (onduleur
      réseau d'un devis « les deux »), ``'avec'`` (hybride d'un devis « les deux ») ;
    * ``motif`` / ``message`` — en repli seulement, la raison (sans sujet, pour l'aperçu) et
      la phrase complète (journal de la génération) ;
    * ``batterie_a_verifier`` — l'onduleur porte la batterie du devis : la génération JUGE la
      batterie par la composition elle-même (:func:`_batterie_composee`), et se replie si elle
      n'en pose aucune (relecture, point 3 : jamais une option « avec » sans batterie).

    Ce qu'une forme peut porter : site isolé ⇒ l'autonome seul ; « sans » ⇒ un onduleur réseau
    (un hybride sans batterie reste en repli : non tranché) ; « avec » ⇒ un hybride servi par une
    batterie tarifée ; « les deux » ⇒ le réseau à l'option sans, l'hybride à l'option avec.

    ``famille_au_nom`` (:func:`famille_lue_au_nom`) — une famille de rôle / fiche que le NOM ne
    dit pas n'est pas imposée : le PDF ne rendrait pas l'option, la resynchronisation en
    ajouterait un second (repli annoncé, « son nom ne dit pas… »).

    ``phase_client`` (``'monophase'`` / ``'triphase'`` / ``None``) et ``triphase`` (le produit,
    ``compatibilites.est_triphase_produit``) — la règle du raccordement que le choix du catalogue
    applique (``composition._vivier_onduleurs_par_phase`` : L-TRI, jamais de monophasé chez un
    client triphasé ; un triphasé écarté chez un client monophasé) : un onduleur désigné ne la
    contourne pas (repli annoncé).

    ``nombre`` — le nombre d'onduleurs que le CALEPINAGE retient (accepté à l'étape Électrique,
    sinon celui de son schéma), jamais la règle du catalogue : sans lui (``None``) ou illisible
    (``nombre_illisible``), repli annoncé — le devis et le schéma ne se contrediront pas."""
    motif = None if etat == 'tarife' else etat
    nom_muet = famille is not None and famille_au_nom != famille
    if motif is None:
        if famille is None:
            motif = 'non_onduleur'
        elif nom_muet:
            motif = 'nom_muet'
        elif hors_reseau:
            motif = None if famille == 'onduleur_offgrid' else 'site_isole'
        elif famille == 'onduleur_offgrid':
            motif = 'autonome_raccorde'
        elif famille == 'onduleur_reseau' and scenario == COMPOSITION_AVEC:
            motif = 'reseau_avec_batterie'
        elif famille == 'onduleur_hybride' and scenario == COMPOSITION_SANS:
            motif = 'hybride_sans_batterie'
    if motif is None and phase_client == 'triphase' and triphase is False:
        motif = 'mono_sur_tri'
    elif motif is None and phase_client == 'monophase' and triphase:
        motif = 'tri_sur_mono'
    if motif is None and (nombre_illisible or not _nombre_valide(nombre)):
        motif = 'nombre_illisible' if nombre_illisible else 'nombre_inconnu'
    if motif is not None:
        return repli_onduleur_designe(nom, motif, famille)
    option = ''
    if scenario == COMPOSITION_LES_DEUX and not hors_reseau:
        option = 'sans' if famille == 'onduleur_reseau' else 'avec'
    porte_la_batterie = famille in ('onduleur_hybride', 'onduleur_offgrid') and (
        hors_reseau or scenario in (COMPOSITION_AVEC, COMPOSITION_LES_DEUX))
    return {'impose': {'produit_id': int(produit_id), 'categorie': famille, 'nombre': int(nombre)},
            'option': option, 'nom': nom, 'batterie_a_verifier': porte_la_batterie,
            'motif': None, 'message': None}


def _batterie_composee(intention):
    """Relecture D-ACAL-148, point 3 — la composition (``etape_composer.composer``, sur
    l'intention que ``pipeline.intention_de_composition`` traduit) pose-t-elle une batterie avec
    l'onduleur désigné ? Scénario « avec » : le kit de l'option « avec » d'un devis « les deux »
    est cette même composition mono-option (``composition_deux_optimiseurs``). Aucune règle de
    batterie n'est recopiée ici ; lecture seule."""
    from apps.ventes.domain.pipeline import intention_de_composition

    essai = intention_de_composition(replace(intention, scenario=COMPOSITION_AVEC), intention.cible,
                                     avertissements=[], devis=None)
    return 'batterie' in (getattr(composer(essai), 'roles', ()) or ())


def _nombre_valide(nombre):
    """Un nombre d'onduleurs exploitable : un entier (jamais un booléen) d'au moins 1."""
    return isinstance(nombre, int) and not isinstance(nombre, bool) and nombre >= 1


def onduleur_designe_pour_le_devis(company, designe, *, scenario, hors_reseau, phase=None):
    """D-ACAL-148 — la décision (:func:`decision_onduleur_designe`) pour l'onduleur désigné
    ``designe`` (``{'produit_id', 'nombre'}`` de l'étape Électrique), lue sur le catalogue de
    vente de la société (le vivier de la composition : produits de la société et globaux, non
    archivés), sa fiche et ses batteries. ``None`` sans désignation. Lecture seule. ``phase`` : le
    raccordement du lead (celui que reçoit la composition)."""
    from apps.ventes.compatibilites import est_triphase_produit, normaliser_phase
    from apps.stock.selectors import get_produit_scoped, specs_for_produit

    from apps.ventes.domain.catalogue import est_article_pompage

    if not designe:
        return None
    try:
        cle = int(designe.get('produit_id'))
    except (TypeError, ValueError):
        return repli_onduleur_designe('fiche produit %s' % designe.get('produit_id'), 'introuvable')
    produit = next((p for p in catalogue_de_la_societe(company) if getattr(p, 'pk', None) == cle), None)
    if produit is None:
        lu = get_produit_scoped(company, cle)
        nom, etat = (getattr(lu, 'nom', None) or 'fiche produit #%s' % cle), 'introuvable'
    else:
        nom = produit.nom
        etat = ('sans_prix' if not _has_price(produit)
                else 'pompage' if est_article_pompage(produit) else 'tarife')
    famille = (famille_onduleur_du_produit(produit, specs_for_produit(produit) or {})
               if etat == 'tarife' else None)
    return decision_onduleur_designe(
        produit_id=cle, nom=nom, etat=etat, famille=famille, famille_au_nom=famille_lue_au_nom(nom),
        scenario=scenario,
        hors_reseau=hors_reseau, nombre=(designe or {}).get('nombre'),
        nombre_illisible=bool((designe or {}).get('nombre_illisible')),
        phase_client=normaliser_phase(phase),
        triphase=bool(est_triphase_produit(produit)) if produit is not None else None)


def build_devis_from_layout(*, layout, user, company, lead=None, client=None,
                            taux_tva=None, remise_globale=Decimal('0'),
                            deux_options=False, journal=None, phase=None,
                            dimensionnement_avec=None,
                            mppt_paires=1, structure_type=None,
                            structure_produit_id=None, hors_reseau=None, a_blanc=False,
                            onduleur_designe=None):
    """Q3 — turn a FINALISED roof layout into a coherent, company-scoped Devis.

    ``onduleur_designe`` (D-ACAL-148, fondateur 26/11/2026) — l'onduleur DÉSIGNÉ à l'étape
    Électrique du calepinage, ``{'produit_id', 'nombre'}`` : le devis le chiffre quand il est au
    catalogue avec un prix et que la forme du devis peut le porter
    (:func:`decision_onduleur_designe`), sinon il garde l'onduleur de la composition et le DIT
    (``journal['avertissements']``). ``journal['onduleur_designe']`` reçoit la décision (aussi
    à blanc : l'aperçu la lit). ``None`` (LE DÉFAUT) ⇒ composition inchangée.

    ``a_blanc`` (lane E9, T4-X5-010) — LE DRY-RUN de ce même chemin : aucun client résolu
    (``resolve_client_for_lead`` écrit), aucun devis ; la composition des étapes 1-4 du
    pipeline (``composer_l_intention``) est rendue en specs de lignes
    (``specs_de_composition``) — ce que l'appel écrirait, sans une seconde composition.

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
    marche = _marche_du_lead(lead)  # ACON40 — avant toute écriture
    # APAR49 — taux absent ⇒ taux STANDARD de la société (jamais 20 codé).
    if taux_tva is None:
        from apps.ventes.utils.company_settings import tva_standard
        taux_tva = tva_standard(company)
    # STKCAT8/STKCAT9 (bis) — le chemin 3D suit la MÊME règle que /auto/ :
    # le choix imposé par l'appelant d'abord, sinon la structure épinglée
    # sur le lead, sinon sa préférence acier/aluminium, sinon acier (le
    # défaut historique — un appelant qui passe 'acier' compose comme hier).
    structure_produit_id, structure_type = _structure_demandee(
        lead, structure_produit_id, structure_type)
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

    if client is None and not a_blanc:
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
    # D-ACAL-148 — l'onduleur désigné, jugé sur la forme RETENUE (scénario, site isolé).
    designe = (onduleur_designe_pour_le_devis(company, onduleur_designe, scenario=scenario,
                                              hors_reseau=hors_reseau, phase=phase)
               if onduleur_designe else None)

    # ── QJR95 — LE PIPELINE, DANS SON ORDRE UNIQUE ─────────────────────────
    # La cible est SOUVERAINE : elle vient du toit que le commercial a dessiné,
    # et l'étape 2 ne redimensionne donc rien. Le scénario du layout est dit
    # dans le SEUL vocabulaire du pipeline — ``deux_options`` l'emporte, comme
    # le faisait déjà la composition (où ``avec_batterie`` n'a aucun effet dès
    # que la forme est à deux options). PVCOMPAT (``phase``), QJR80
    # (``mppt_paires`` / ``structure_type``) et L-2OPT (``dimensionnement_avec``)
    # sont transmis par les mêmes champs que les quatre autres origines.
    intention = IntentionDevis(
        origine=ORIGINE_CALEPINAGE,
        company=company,
        user=user,
        lead=lead,
        client=client,
        mode_installation=marche,  # ACON40 — le marché du lead
        cible=CibleDevis(
            nb_panneaux=nb_panneaux,
            panel_watt=watt,
            kwc=kwc_composition,
            source='calepinage',
            dimensionnement_avec=dimensionnement_avec,
            # ACAL63 — le devis vend le(s) module(s) DÉSIGNÉ(S) par le
            # calepinage : une ligne panneau par modèle (``None`` sans fiche
            # désignée ⇒ composition au wattage, inchangée).
            modeles=modeles_designes(layout) or None,
            onduleur_impose=designe['impose'] if designe is not None else None),
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
    )
    if (designe is not None and designe['impose'] and designe['batterie_a_verifier']
            and not _batterie_composee(intention)):
        # Point 3 — la composition ne poserait aucune batterie : jamais une option « avec »
        # sans batterie ni une option retirée en silence ; le choix du catalogue, dit.
        designe = repli_onduleur_designe(designe['nom'], 'batterie_non_composee')
        intention = replace(intention, scenario=scenario, cible=replace(intention.cible, onduleur_impose=None))
    if journal is not None and designe is not None:
        journal['onduleur_designe'] = designe
    annonces = [designe['message']] if designe is not None and designe['message'] else []
    if a_blanc:
        from apps.ventes.domain.pipeline import composer_l_intention, specs_de_composition

        return specs_de_composition(composer_l_intention(None, intention, [])[2])
    resultat = appliquer(None, intention)
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
        journal['avertissements'] = list(avertissements or ()) + annonces
        journal['nb_panneaux'] = getattr(line_specs, 'nb_panneaux', 0)
        journal['kwc_reel'] = getattr(line_specs, 'kwc_reel', 0.0)
    elif avertissements or annonces:
        # Sans canal fourni, la composition journalisait elle-même ses refus.
        # Le pipeline, lui, les COLLECTE toujours : on les journalise ici
        # plutôt que de les laisser dans une liste que personne ne lit.
        for message in [*(avertissements or ()), *annonces]:
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


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.catalogue import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _has_price,
    catalogue_de_la_societe,
    classer_produit,
)
from apps.ventes.domain.geometrie import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    arbitrer_compte_calepinage,
    lire_layout,
    modeles_designes,
)
from apps.ventes.domain.pipeline import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    ORIGINE_CALEPINAGE,
    CibleDevis,
    IntentionDevis,
    appliquer,
)
from apps.ventes.domain.etape_composer import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    composer,
    COMPOSITION_AVEC,
    COMPOSITION_LES_DEUX,
    COMPOSITION_SANS,
    MSG_AUCUN_PANNEAU,
    IntentionComposition,
    verifier,
)
from apps.ventes.domain.taille import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    AutoDevisError,
    phase_et_isolement_du_lead,
)
# ``_structure_demandee`` reste dans ``creation`` (aussi lu par le devis
# automatique) ; ``creation`` ne lit ce module que pour le devis automatique.
from apps.ventes.domain.creation import _structure_demandee  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
