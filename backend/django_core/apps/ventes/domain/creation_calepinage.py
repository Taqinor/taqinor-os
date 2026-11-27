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


def toiture_sans_suppositions(toiture):
    """La toiture à RANGER (``etude_params['toiture']``, servi au client comme ``data['etude']``) :
    sans ``suppositions`` (D-ACAL-149 (ii)) ; round 4, point 3 — sans l'inclinaison SUPPOSÉE
    (D-ACAL-168 : jamais imprimée pour le client) ni le drapeau privé, pan par pan et pour le pan
    principal ; la production lit ``_pans_geometry``, qui la garde. Une copie ;
    ``phrases_des_suppositions`` rend la phrase au vendeur."""
    from apps.ventes.domain.geometrie import CLE_INCLINAISON_SUPPOSEE

    rangee = {cle: valeur for cle, valeur in (toiture or {}).items() if cle != 'suppositions'}
    if (toiture or {}).get('suppositions'):
        rangee.pop('inclinaison_deg', None)
    if isinstance(rangee.get('pans'), list):
        rangee['pans'] = [{cle: valeur for cle, valeur in pan.items()
                           if cle != CLE_INCLINAISON_SUPPOSEE and not (
                               pan.get(CLE_INCLINAISON_SUPPOSEE) and cle == 'inclinaison_deg')}
                          if isinstance(pan, dict) else pan for pan in rangee['pans']]
    return rangee


def phrases_des_suppositions(toiture):
    """Les phrases des suppositions de la lecture du toit (D-ACAL-149 / 168), pour ``avertissements``."""
    return [s['message'] for s in (toiture or {}).get('suppositions') or () if s.get('message')]


def _calepinage_range(layout, toiture, kwc, designations=None):
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
    if designations is not None:  # D-ACAL-148 — clé privée (ni empreinte, ni page client) ; ``{}`` compris
        layout_stocke[CLE_DESIGNATIONS] = designations
    etude_initiale = {}
    if kwc:
        etude_initiale['puissance_kwc'] = kwc
    if toiture:
        # D-ACAL-149 (ii) — la supposition est une consigne au VENDEUR (``avertissements``) :
        # ``etude_params`` est servi au client (``data['etude']``), elle n'y entre jamais.
        etude_initiale['toiture'] = toiture_sans_suppositions(toiture)
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


def composer_a_blanc_depuis_layout(*, layout, company, lead=None, onduleur_designe=None, journal=None,
                                   batterie_designee=None):
    """Lane E9b — LE dry-run de « Générer le devis » (``build_devis_from_layout(a_blanc=True)``)
    sous ``conception.moteur.reglages_lus_sans_creer`` : la TVA et le tarif de la société sont
    lus sur la ligne existante, sinon sur une instance NON enregistrée — un ``GET`` ne crée
    jamais de ``CompanyProfile`` / ``TariffSettings``. Rend les specs de lignes.

    D-ACAL-148 — ``onduleur_designe`` / ``journal`` : ceux de la génération (même décision,
    rangée dans ``journal['onduleur_designe']``)."""
    from apps.ventes.conception.moteur import reglages_lus_sans_creer

    with reglages_lus_sans_creer(company):
        return build_devis_from_layout(layout=layout, user=None, company=company, lead=lead, a_blanc=True,
                                       onduleur_designe=onduleur_designe, journal=journal,
                                       batterie_designee=batterie_designee)


# ── D-ACAL-148 — L'ONDULEUR DÉSIGNÉ À L'ÉTAPE ÉLECTRIQUE ─────────────────────
#: Clé PRIVÉE de ``Devis.roof_layout`` (préfixe ``_`` : hors ``layout_hash``, hors page client
#: ``public_views._safe_roof_layout``, jamais recopiée dans un calepinage) : la désignation
#: appliquée par la création ou la dernière resynchronisation.
CLE_DESIGNATIONS = '_designations'
#: Les trois familles d'onduleur qu'une composition résidentielle sait vendre.
FAMILLES_ONDULEUR_DESIGNABLES = ('onduleur_reseau', 'onduleur_hybride', 'onduleur_offgrid')
#: La suite de toute phrase de repli : ce que le devis fait à la place.
SUITE_REPLI_ONDULEUR = 'le devis garde l’onduleur de la conception du lead'
MESSAGE_ONDULEUR_NON_CHIFFRE = ('L’onduleur désigné à l’étape Électrique (« %s ») n’est pas chiffré : %s ; '
                                + SUITE_REPLI_ONDULEUR + '.')
#: D-ACAL-159 (fondateur, 26/11/2026) — un hybride désigné sur un devis « sans batterie » le fait
#: passer en « avec batterie » ; la phrase dite au vendeur (génération et aperçu).
MESSAGE_BASCULE_AVEC_BATTERIE = 'Le devis passe en « avec batterie » : l’onduleur désigné « %s » est un hybride.'
MOTIFS_REPLI_ONDULEUR = {
    'introuvable': 'il n’est pas au catalogue de vente de la société (inconnu ou archivé)',
    'sans_prix': 'il n’a pas de prix de vente au catalogue',
    'pompage': 'c’est un article de pompage',
    'non_onduleur': ('il n’est reconnu comme onduleur réseau, hybride ou hors réseau ni par son rôle, '
                     'ni par sa fiche, ni par son nom'),
    'site_isole': 'le site est hors réseau : seul un onduleur hors réseau (autonome) peut être chiffré',
    'autonome_raccorde': 'c’est un onduleur hors réseau et le site est raccordé au réseau',
    'reseau_avec_batterie': 'c’est un onduleur réseau : il ne porte pas la batterie de ce devis',
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
    return {'impose': None, 'option': None, 'nom': nom, 'batterie_a_verifier': False, 'raison': texte,
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

    Ce qu'une forme peut porter : site isolé ⇒ l'autonome seul ; « sans » ⇒ un onduleur réseau, et
    un hybride y fait passer le devis « avec batterie » (D-ACAL-159 : ``scenario`` rendu =
    ``'avec'``, ``message`` = :data:`MESSAGE_BASCULE_AVEC_BATTERIE`) ; « avec » ⇒ un hybride ;
    « les deux » ⇒ le réseau à l'option sans, l'hybride à l'option avec (inchangé).

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
    # D-ACAL-159 — un hybride sur un devis « sans batterie » le fait passer « avec batterie » (la
    # batterie : celle que la composition pose par sa propre règle, jugée par la génération).
    bascule = famille == 'onduleur_hybride' and scenario == COMPOSITION_SANS and not hors_reseau
    compose = COMPOSITION_AVEC if bascule else scenario
    porte_la_batterie = famille in ('onduleur_hybride', 'onduleur_offgrid') and (
        hors_reseau or compose in (COMPOSITION_AVEC, COMPOSITION_LES_DEUX))
    return {'impose': {'produit_id': int(produit_id), 'categorie': famille, 'nombre': int(nombre)},
            'option': option, 'nom': nom, 'batterie_a_verifier': porte_la_batterie, 'scenario': compose,
            'motif': None, 'message': MESSAGE_BASCULE_AVEC_BATTERIE % nom if bascule else None}


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


def juger_la_batterie(decision, intention):
    """Point 3 — la décision, ou son repli « aucune batterie composée » quand l'onduleur désigné
    porte la batterie et que la composition (:func:`_batterie_composee`) n'en pose aucune avec
    lui. Même juge à la création et à la resynchronisation."""
    if (decision is not None and decision['impose'] and decision['batterie_a_verifier']
            and not _batterie_composee(intention)):
        return repli_onduleur_designe(decision['nom'], 'batterie_non_composee')
    return decision


def marqueur_des_designations(decision, batterie=None):
    """Le marqueur PRIVÉ de ``roof_layout`` (:data:`CLE_DESIGNATIONS`) : l'onduleur et la batterie
    désignés que le devis porte (``None`` quand aucun ne l'est), relu par la resynchronisation pour
    savoir ce qui a changé."""
    marqueur = {cle: d['impose']['produit_id'] for cle, d in (('onduleur', decision), ('batterie', batterie))
                if d is not None and d['impose']}
    return {'onduleur': marqueur.get('onduleur'), 'batterie': marqueur.get('batterie')} if marqueur else None


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


# ── D-ACAL-164 (fondateur, 26/11/2026) — LA BATTERIE DÉSIGNÉE À L'ÉTAPE ÉLECTRIQUE ──────────
MESSAGE_BATTERIE_NON_CHIFFREE = ('La batterie désignée à l’étape Électrique (« %s ») n’est pas chiffrée : %s ; '
                                 'le devis garde le choix automatique de la batterie.')
MESSAGE_BATTERIE_SANS = ('La batterie désignée à l’étape Électrique (« %s ») n’est pas mise au devis : le devis est '
                         '« sans batterie » et aucun onduleur hybride n’est désigné.')
MOTIFS_REPLI_BATTERIE = {
    'introuvable': 'elle n’est pas au catalogue de vente de la société (inconnue ou archivée)',
    'sans_prix': 'elle n’a pas de prix de vente au catalogue',
    'pompage': 'c’est un article de pompage',
    'nom_muet': ('son nom ne dit pas qu’il s’agit d’une batterie : le PDF du devis et la resynchronisation '
                 'reconnaissent une batterie à son nom'),
    'sans_hybride': 'aucun onduleur hybride ni autonome n’est mis au devis pour la porter',
    'incompatible': 'elle ne convient pas à l’onduleur « %s » (plage batterie de sa fiche)',
    'packs_illisible': 'le nombre de packs saisi à l’étape Électrique n’est pas un entier d’au moins 1',
    'packs_inconnu': 'aucun nombre de packs n’est saisi à l’étape Électrique',
    'packs_plafond': ('le nombre de packs saisi (%d) dépasse les %d modules par banc de sa fiche : la '
                      'composition ne pose jamais un tel banc'),
}
#: Relecture round 4, point 4 — le nombre DÉSIGNÉ est vendu (D-ACAL-164) ; quand la règle automatique
#: poserait un autre nombre de modules de cette même batterie, les deux nombres sont dits.
MESSAGE_PACKS_ECART = ('La batterie désignée « %s » est vendue à %d pack(s), le nombre saisi à l’étape Électrique ; '
                       'la règle automatique du devis en placerait %d.')


def decision_batterie_designee(*, produit_id, nom, etat, nom_dit_batterie, scenario, hybride_nom, compatible,
                               packs=None, packs_illisible=False, plafond=None):
    """D-ACAL-164 — que fait le devis de la batterie DÉSIGNÉE ? Fonction PURE, sœur de
    :func:`decision_onduleur_designe`. ``scenario`` : celui que le devis COMPOSE (après la décision
    de l'onduleur, D-ACAL-159 compris) ; ``hybride_nom`` : l'onduleur qui la porterait (désigné, sinon
    celui que la composition pose), ``None`` sans hybride ; ``compatible`` : le juge de la composition
    (``catalogue._batterie_compatible`` sur la plage de cet onduleur) ; ``packs`` : le nombre saisi.

    « sans batterie » ⇒ non mise au devis, dit (D-ACAL-159 n'est pas étendu) ; prix, nom, onduleur,
    compatibilité, packs : sinon repli dit (le choix automatique) ; sinon ``impose`` =
    ``{'produit_id', 'nombre', 'designee'}`` (``batterie_imposee`` de la composition), à l'option
    « avec » d'un devis « les deux ». Comme l'onduleur désigné : un prix suffit, le stock n'est pas
    exigé (la banque imposée de la composition ne lit pas le stock)."""
    if scenario == COMPOSITION_SANS:
        return {'impose': None, 'option': None, 'motif': 'sans', 'nom': nom, 'raison': None,
                'message': MESSAGE_BATTERIE_SANS % nom}
    motif = None if etat == 'tarife' else etat
    if motif is None:
        if not nom_dit_batterie:
            motif = 'nom_muet'
        elif hybride_nom is None:
            motif = 'sans_hybride'
        elif not compatible:
            motif = 'incompatible'
        elif packs_illisible:
            motif = 'packs_illisible'
        elif not _nombre_valide(packs):
            motif = 'packs_inconnu'
        elif plafond is not None and packs > plafond:  # point 4 — ``catalogue._max_modules_par_banc``
            motif = 'packs_plafond'
    if motif is not None:
        texte = MOTIFS_REPLI_BATTERIE[motif] % ((hybride_nom,) if motif == 'incompatible'
                                                else (packs, plafond) if motif == 'packs_plafond' else ())
        return {'impose': None, 'option': None, 'motif': motif, 'nom': nom, 'raison': texte,
                'message': MESSAGE_BATTERIE_NON_CHIFFREE % (nom, texte)}
    return {'impose': {'produit_id': int(produit_id), 'nombre': int(packs), 'designee': True}, 'nom': nom,
            'option': 'avec' if scenario == COMPOSITION_LES_DEUX else '', 'motif': None, 'raison': None,
            'message': None}


def batterie_designee_pour_le_devis(company, designe, *, scenario, hybride):
    """D-ACAL-164 — :func:`decision_batterie_designee` pour ``designe`` (``{'produit_id', 'packs',
    'packs_illisible'}`` de l'étape Électrique), lue sur le catalogue de vente de la société ;
    ``hybride`` : le produit onduleur qui la porterait. ``None`` sans désignation. Lecture seule."""
    from apps.stock.selectors import get_produit_scoped

    from apps.ventes.domain.catalogue import (
        _batterie_compatible, _is_battery, _max_modules_par_banc, _plage_batterie_de_l_onduleur, est_article_pompage)
    from apps.ventes.utils.options import texte_classement

    if not designe:
        return None
    try:
        cle = int(designe.get('produit_id'))
    except (TypeError, ValueError):
        cle = None
    produit = next((p for p in catalogue_de_la_societe(company) if getattr(p, 'pk', None) == cle), None)
    if produit is None:
        lu = get_produit_scoped(company, cle) if cle is not None else None
        nom, etat = (getattr(lu, 'nom', None) or 'fiche produit #%s' % designe.get('produit_id')), 'introuvable'
    else:
        nom = produit.nom
        etat = ('sans_prix' if not _has_price(produit)
                else 'pompage' if est_article_pompage(produit) else 'tarife')
    compatible = (etat == 'tarife' and hybride is not None
                  and _batterie_compatible(produit, _plage_batterie_de_l_onduleur(hybride)))
    return decision_batterie_designee(
        produit_id=cle, nom=nom, etat=etat, nom_dit_batterie=_is_battery(texte_classement(nom, nom)),
        scenario=scenario, hybride_nom=getattr(hybride, 'nom', None), compatible=bool(compatible),
        packs=designe.get('packs'), packs_illisible=bool(designe.get('packs_illisible')),
        plafond=_max_modules_par_banc(produit) if etat == 'tarife' else None)


def _onduleur_de_stockage_compose(intention):
    """L'onduleur hybride (ou autonome) que la composition pose avec une batterie — la MÊME
    composition que la création (scénario « avec », kit de l'option avec d'un « les deux »), sans
    batterie imposée ; ``None`` s'il n'y en a pas. Lecture seule."""
    from apps.ventes.domain.pipeline import intention_de_composition

    essai = intention_de_composition(
        replace(intention, scenario=COMPOSITION_AVEC, cible=replace(intention.cible, batterie_imposee=None)),
        replace(intention.cible, batterie_imposee=None), avertissements=[], devis=None)
    lignes = composer(essai)
    roles = list(getattr(lignes, 'roles', ()) or ())
    return next((ligne.produit for role, ligne in zip(roles, lignes)
                 if role in ('onduleur_hybride', 'onduleur_offgrid')), None)


def _banque_automatique(intention, produit):
    """Point 4 — le nombre de modules que la RÈGLE AUTOMATIQUE poserait pour cette même batterie :
    la vraie composition « avec », sans banque imposée, calibre épinglé sur celui de la batterie
    (``batterie_module_kwh``, le pin BATHOMO de la composition). ``None`` sans calibre lisible ou
    sans batterie composée. Lecture seule.

    Pré-CI lot 8 — la règle est jugée sur CETTE batterie seule : le vivier de la composition préfère
    les Dyness (et suit la marque de batterie épinglée), si bien qu'une autre batterie désignée n'y
    entrait jamais, le pin restait sans correspondance et l'écart n'était pas dit. Le catalogue de
    l'essai ne garde donc, comme batterie, que la désignée ; tout le reste (cible, onduleur, plafond)
    est la vraie composition."""
    from apps.ventes.domain.etape_composer import reglages_de_composition
    from apps.ventes.domain.kwh_lecture import _parse_kwh
    from apps.ventes.domain.pipeline import intention_de_composition

    calibre = _parse_kwh(getattr(produit, 'nom', '') or '')
    if not calibre:
        return None
    cible = replace(intention.cible, batterie_imposee=None)
    essai = intention_de_composition(replace(intention, scenario=COMPOSITION_AVEC, cible=cible), cible,
                                     avertissements=[], devis=None)
    base = reglages_de_composition(essai.company, essai.gamme_nom_devis)
    seule = replace(base, marques={r: m for r, m in (base.marques or {}).items() if r != 'batterie'},
                    catalogue=[p for p in base.catalogue if getattr(p, 'pk', None) == produit.pk
                               or classer_produit(getattr(p, 'nom', '') or '') != 'batterie'])
    lignes = composer(replace(essai, batterie_module_kwh=calibre, reglages=seule))
    roles = list(getattr(lignes, 'roles', ()) or ())
    return sum(int(ligne.quantite) for role, ligne in zip(roles, lignes) if role == 'batterie') or None


def _decider_la_batterie(intention, brute):
    """La décision batterie de la création, jugée sur l'onduleur que CE devis porterait ; point 4 —
    les packs désignés sont vendus, et l'écart à la règle automatique est dit."""
    from apps.ventes.domain.etape_composer import _fiche_tarifee

    if not brute:
        return None
    scenario = (intention.scenario or '').strip().lower()
    hybride = None if scenario == COMPOSITION_SANS else _onduleur_de_stockage_compose(intention)
    decision = batterie_designee_pour_le_devis(intention.company, brute, scenario=scenario, hybride=hybride)
    if decision is not None and decision['impose']:
        auto = _banque_automatique(intention, _fiche_tarifee(intention.company, decision['impose']['produit_id']))
        if auto is not None and auto != decision['impose']['nombre']:
            decision = dict(decision, message=MESSAGE_PACKS_ECART % (decision['nom'], decision['impose']['nombre'],
                                                                     auto))
    return decision


def _avec_la_batterie(intention, batterie):
    impose = batterie['impose'] if batterie is not None else None
    return replace(intention, cible=replace(intention.cible, batterie_imposee=impose))


def _appliquer_les_designations(intention, designe, batterie_brute, scenario, journal, *, marquer=False):
    """D-ACAL-148 / 159 / 164 — à la création : la batterie désignée jugée sur l'onduleur du devis,
    la batterie de l'onduleur désigné jugée par la composition (:func:`juger_la_batterie` ; repli :
    scénario d'origine, et la batterie re-jugée), le marqueur privé, le journal et les phrases.
    ``marquer`` (relecture, point 1) : création depuis un calepinage — le marqueur est posé même
    vide (``{}`` : le devis est NÉ sous la règle). Rend ``(intention, annonces)``."""
    batterie = _decider_la_batterie(intention, batterie_brute)
    intention = _avec_la_batterie(intention, batterie)
    designe = juger_la_batterie(designe, intention)
    if designe is not None and not designe['impose'] and intention.cible.onduleur_impose is not None:
        # Point 3 — repli : le scénario d'origine et le choix du catalogue, dits.
        intention = replace(intention, scenario=scenario, cible=replace(
            intention.cible, onduleur_impose=None, batterie_imposee=None))
        batterie = _decider_la_batterie(intention, batterie_brute)
        intention = _avec_la_batterie(intention, batterie)
    marqueur = marqueur_des_designations(designe, batterie)
    if marqueur or marquer:  # la désignation APPLIQUÉE (``{}`` : aucune), relue par la resynchro
        intention = replace(intention, layout=dict(intention.layout, **{CLE_DESIGNATIONS: marqueur or {}}))
    if journal is not None:
        journal.update({cle: d for cle, d in (('onduleur_designe', designe), ('batterie_designee', batterie))
                        if d is not None})
    return intention, [d['message'] for d in (designe, batterie) if d is not None and d['message']]


# ── D-ACAL-148 / 159 / 164 (relecture, A) — LA RESYNCHRONISATION APPLIQUE LA MÊME DÉCISION ─────
#: ``CibleDevis.source`` d'une resynchronisation qui porte les désignations BRUTES du calepinage
#: (mode « réconcilier » : ``reconcilier`` est le seul lecteur de la cible).
SOURCE_DESIGNATIONS = 'designations_calepinage'
#: Revue du 26/11 (D-ACAL-73) — les mêmes désignations, portées par une resynchronisation que le vendeur a
#: CONFIRMÉE sur la carte d'aperçu (``apercu_confirme``) : seule celle-ci les applique à un devis ENVOYÉ.
SOURCE_DESIGNATIONS_CONFIRMEES = 'designations_calepinage_confirmees'
SOURCES_DESIGNATIONS = (SOURCE_DESIGNATIONS, SOURCE_DESIGNATIONS_CONFIRMEES)
MSG_RESYNC_SUIT = 'L’onduleur suit la désignation de l’étape Électrique : « %s » remplace « %s ».'
MSG_RESYNC_CHANGE = 'La désignation de l’onduleur a changé à l’étape Électrique : « %s » remplace « %s ».'
MSG_RESYNC_RETIREE = ('L’onduleur « %s » n’est plus désigné à l’étape Électrique : la resynchronisation '
                      'reprend le choix du catalogue (« %s »).')
MSG_RESYNC_RETIREE_REGLE = ('L’onduleur « %s » n’est plus désigné à l’étape Électrique : la '
                            'resynchronisation reprend la règle du catalogue.')
#: Relecture (point 6 b / d) — la désignation est toujours là, mais n'est plus chiffrable : ce que la
#: resynchronisation fait de la ligne ACTUELLE, dit dans la même phrase que la raison.
MSG_RESYNC_NON_CHIFFRE_REPRISE = ('L’onduleur désigné à l’étape Électrique (« %s ») n’est plus chiffrable : %s ; la '
                                  'resynchronisation reprend le choix du catalogue (« %s »).')
MSG_RESYNC_NON_CHIFFRE_REGLE = ('L’onduleur désigné à l’étape Électrique (« %s ») n’est plus chiffrable : %s ; la '
                                'resynchronisation reprend la règle du catalogue.')
MSG_RESYNC_NON_APPLIQUE = ('L’onduleur désigné à l’étape Électrique (« %s ») n’est pas appliqué : %s ; le devis '
                           'garde son onduleur actuel%s.')
MSG_RESYNC_PRIX_MANUEL = ('Prix saisi à la main sur « %s » : « %s » n’a pas été posé à sa place '
                          '— remplacez-le à la main s’il le faut.')
MSG_RESYNC_QUANTITE_MANUELLE = ('Quantité saisie à la main sur « %s » : la ligne est gardée telle quelle '
                                '— retirez-la à la main s’il le faut.')
#: Relecture (point 2) — la ligne a été changée À LA MAIN depuis que la désignation a été appliquée.
MSG_RESYNC_CHANGE_A_LA_MAIN = ('« %s » a été posé à la main à la place de l’onduleur désigné « %s » : la '
                               'resynchronisation garde le choix fait à la main.')
MSG_RESYNC_BATTERIE_A_LA_MAIN = ('« %s » a été posée à la main à la place de la batterie désignée « %s » : la '
                                 'resynchronisation garde le choix fait à la main.')
#: Relecture (point 1) — la règle n'est appliquée qu'aux brouillons nés sous elle.
MSG_RESYNC_AVANT_LA_REGLE = ('Le calepinage désigne %s à l’étape Électrique : ce devis, créé avant que le devis '
                             'suive la désignation, ne la suit pas ; un nouveau devis généré depuis le calepinage '
                             'la suivra.')
#: ACAL1320 (D-ACAL-73 = corriger_dire, 26/11/2026) — les statuts dont la resynchronisation corrige
#: le devis SUR PLACE (règle QJR5 ; un envoyé, sa trace « corrigé après envoi » posée, et l'écran le
#: dit AVANT d'agir par l'aperçu) : un devis né sous la règle y suit la désignation. La phrase
#: « révisez-le (V2) » d'un envoyé est retirée : elle n'était vraie pour aucun devis (une V2 d'un devis
#: sans marqueur n'en porte pas davantage). Revue du 26/11 — l'envoyé ne la suit QUE par une
#: resynchronisation confirmée sur l'aperçu (:data:`SOURCE_DESIGNATIONS_CONFIRMEES`).
STATUTS_CORRIGES_SUR_PLACE = ('brouillon', 'envoye')
MSG_RESYNC_ENVOYE_SANS_APERCU = ('Le calepinage désigne %s à l’étape Électrique : sur un devis envoyé, la '
                                 'désignation n’est appliquée qu’après son aperçu — utilisez « Resynchroniser le '
                                 'devis » dans l’atelier pour voir le changement et le confirmer.')
MSG_RESYNC_BATTERIE_SUIT = 'La batterie suit la désignation de l’étape Électrique : « %s » (%d pack(s)).'
MSG_RESYNC_BATTERIE_RETIREE = ('La batterie « %s » n’est plus désignée à l’étape Électrique : la '
                               'resynchronisation reprend le choix automatique de la batterie.')
MSG_RESYNC_BATTERIE_NON_CHIFFREE_REPRISE = ('La batterie désignée à l’étape Électrique (« %s ») n’est plus '
                                            'chiffrable : %s ; la resynchronisation reprend le choix automatique '
                                            'de la batterie.')
MSG_RESYNC_BATTERIE_NON_APPLIQUEE = ('La batterie désignée à l’étape Électrique (« %s ») n’est pas appliquée : %s ; '
                                     '%s.')


def cible_des_designations(onduleur_designe, batterie_designee=None, *, apercu_confirme=False):
    """La ``CibleDevis`` d'une resynchronisation depuis le calepinage : les désignations BRUTES
    (``calepinage.services.devis._onduleur_designe`` / ``_batterie_designee``), jugées dans
    ``reconcilier`` par :func:`appliquer_designations_a_la_resynchro`. ``apercu_confirme`` : la
    resynchronisation a été confirmée sur la carte d'aperçu (seule à pouvoir corriger un envoyé)."""
    return CibleDevis(source=SOURCE_DESIGNATIONS_CONFIRMEES if apercu_confirme else SOURCE_DESIGNATIONS,
                      onduleur_impose=onduleur_designe, batterie_imposee=batterie_designee)


def marqueur_stocke(devis):
    """Le marqueur :data:`CLE_DESIGNATIONS` du devis (``{}`` compris), ou ``None`` s'il n'en porte pas."""
    layout = getattr(devis, 'roof_layout', None)
    marqueur = layout.get(CLE_DESIGNATIONS) if isinstance(layout, dict) else None
    return dict(marqueur) if isinstance(marqueur, dict) else None


def suit_les_designations(devis):
    """Relecture (point 1) — le devis est-il NÉ sous la règle (création depuis un calepinage avec ce
    code : il porte le marqueur, ``{}`` compris) ? Seul un tel BROUILLON reçoit les désignations."""
    return marqueur_stocke(devis) is not None


def _quoi_est_designe(cible):
    onduleur, batterie = bool(getattr(cible, 'onduleur_impose', None)), bool(getattr(cible, 'batterie_imposee', None))
    return ('un onduleur et une batterie' if onduleur and batterie else 'un onduleur' if onduleur
            else 'une batterie' if batterie else None)


def _kwc_du_layout(layout):
    from apps.ventes.domain.lignes import LAYOUT_WATT_REPLI

    lecture = lire_layout(layout)
    return lecture, (lecture.kwc or lecture.compte * float(lecture.watt or LAYOUT_WATT_REPLI) / 1000.0)


def _decision_de_resynchro(verrou, layout, designe):
    """``(décision, scénario, phase, isolé)`` de :func:`onduleur_designe_pour_le_devis` pour un devis
    EXISTANT : le scénario du calepinage (« les deux » quand le devis est déclaré « Les deux »), la
    phase et le site isolé du lead, la batterie jugée par :func:`juger_la_batterie` — LES fonctions
    de la création, jamais une seconde règle."""
    from apps.ventes.domain.scenario import SCENARIO_LES_DEUX

    lead = getattr(verrou, 'lead', None)
    phase, isole = phase_et_isolement_du_lead(lead)
    deux = (getattr(verrou, 'etude_params', None) or {}).get('scenario') == SCENARIO_LES_DEUX
    scenario = (COMPOSITION_AVEC if isole else COMPOSITION_LES_DEUX if deux
                else scenario_du_layout(layout))
    decision = (onduleur_designe_pour_le_devis(verrou.company, designe, scenario=scenario,
                                               hors_reseau=isole, phase=phase) if designe else None)
    if decision is not None and decision['impose']:
        lecture, kwc = _kwc_du_layout(layout)
        decision = juger_la_batterie(decision, IntentionDevis(
            origine=ORIGINE_CALEPINAGE, company=verrou.company, lead=lead,
            mode_installation=getattr(verrou, 'mode_installation', None) or 'residentiel',
            cible=CibleDevis(nb_panneaux=lecture.compte, panel_watt=lecture.watt, kwc=kwc, source='calepinage',
                             modeles=modeles_designes(layout) or None, onduleur_impose=decision['impose']),
            scenario=scenario, layout=layout, phase=phase, hors_reseau=isole))
    return decision, scenario, phase, isole


def _famille_de_ligne(ligne):
    return famille_lue_au_nom(ligne.designation or getattr(getattr(ligne, 'produit', None), 'nom', ''))


def _est_onduleur(ligne):
    return (str(getattr(ligne, 'role_devis', '') or '').startswith('onduleur_')
            or _famille_de_ligne(ligne) is not None)


def _poser_produit(ligne, produit, famille, avertissements, *, nombre=None):
    """Pose ``produit`` sur une ligne (produit, désignation, prix catalogue, rôle, et le nombre
    désigné hors quantité saisie à la main) ; un prix saisi à la main n'est jamais écrasé
    (abstention DITE, comme ``reconcilier._permuter_onduleur``). Rend vrai si la ligne a bougé."""
    from apps.ventes.domain.lignes import porter_quantite, poser_prix_unitaire

    if getattr(ligne, 'prix_manuel', False) and ligne.produit_id != produit.pk:
        avertissements.append(MSG_RESYNC_PRIX_MANUEL % (ligne.designation or 'ligne sans désignation',
                                                        produit.nom))
        return False
    champs = []
    if ligne.produit_id != produit.pk:
        ligne.produit, ligne.designation = produit, produit.nom
        poser_prix_unitaire(ligne, Decimal(produit.prix_vente))
        champs += ['produit', 'designation', 'prix_unitaire']
    # Lecteurs en aval — un produit POSÉ (écriture neuve) range sa famille, même sur une ligne sans rôle.
    if (getattr(ligne, 'role_devis', '') or 'produit' in champs) and ligne.role_devis != famille:
        ligne.role_devis = famille
        champs.append('role_devis')
    if champs:
        ligne.save(update_fields=champs)
    if nombre and not getattr(ligne, 'quantite_manuelle', False) and ligne.quantite != Decimal(nombre):
        porter_quantite(ligne, Decimal(nombre))  # QJR6 : l'écrivain sanctionné d'une quantité recalculée
        return True
    return bool(champs)


def _reprendre_le_catalogue(verrou, onduleurs, precedent, veut_batterie, layout, phase, isole, avertissements,
                            *, decision=None):
    """L'onduleur désigné d'AVANT n'est plus appliqué (retiré, ou plus chiffrable — ``decision`` est
    alors son repli) : la ligne qui le porte encore reprend le choix du catalogue
    (``catalogue.choisir_onduleur_permutation``, la règle de ``reconcilier``) ; une famille qui ne suit
    plus le scénario est laissée à ``reconcilier``, qui la permute lui-même. Une ligne déjà changée à
    la main n'est jamais re-choisie (PV18). UNE phrase, vraie dans l'état : la raison quand il est
    toujours désigné, « n'est plus désigné » sinon."""
    from apps.ventes.domain.catalogue import (
        _is_hybrid_inverter, _is_offgrid_inverter, _is_reseau_inverter, choisir_onduleur_permutation)
    from apps.ventes.domain.gammes import gamme_nom

    ligne = next((li for li in onduleurs if li.produit_id == precedent), None)
    if ligne is None:  # déjà changée à la main : gardée (PV18)
        if decision is not None:
            avertissements.append(MSG_RESYNC_NON_APPLIQUE % (decision['nom'], decision['raison'], ''))
        return 0
    famille = _famille_de_ligne(ligne)
    voulue = ('onduleur_offgrid' if isole else famille if scenario_du_layout(layout) == COMPOSITION_LES_DEUX
              else 'onduleur_hybride' if veut_batterie else 'onduleur_reseau')
    predicats = {'onduleur_hybride': _is_hybrid_inverter, 'onduleur_reseau': _is_reseau_inverter,
                 'onduleur_offgrid': _is_offgrid_inverter}
    remplacant = None
    if famille == voulue and voulue in predicats:
        remplacant = choisir_onduleur_permutation(verrou.company, predicats[voulue], kwc=_kwc_du_layout(layout)[1],
                                                  phase=phase, role=voulue, gamme=gamme_nom(verrou))
    ancien = ligne.designation or 'ligne sans désignation'
    if remplacant is None or remplacant.pk == ligne.produit_id:
        avertissements.append(MSG_RESYNC_NON_CHIFFRE_REGLE % (decision['nom'], decision['raison'])
                              if decision else MSG_RESYNC_RETIREE_REGLE % ancien)
        return 0
    if not _poser_produit(ligne, remplacant, voulue, avertissements):
        return 0
    avertissements.append(MSG_RESYNC_NON_CHIFFRE_REPRISE % (decision['nom'], decision['raison'], remplacant.nom)
                          if decision else MSG_RESYNC_RETIREE % (ancien, remplacant.nom))
    return 1


def _a_une_batterie(verrou):
    from apps.ventes.domain.catalogue import _is_battery
    from apps.ventes.domain.lignes import _classe_ligne, _lignes_produit

    return any(_classe_ligne(li, _is_battery) for li in _lignes_produit(verrou))


def _resynchro_inchangee(veut_batterie, stocke):
    return veut_batterie, {'modifiees': 0, 'a_ecrire': False, 'marqueur': stocke}


def designations_appliquees(verrou, intention):
    """Relecture, point 1 — la règle en UN prédicat : la resynchronisation applique les désignations
    seulement quand elles viennent du calepinage (:data:`SOURCES_DESIGNATIONS`) à un devis NÉ sous la
    règle (:func:`suit_les_designations`) : un BROUILLON (toute source du calepinage), ou — ACAL1320
    (D-ACAL-73 = corriger_dire) — un ENVOYÉ seulement par une resynchronisation CONFIRMÉE sur la carte
    d'aperçu (:data:`SOURCE_DESIGNATIONS_CONFIRMEES`). Aucun autre statut (:data:`STATUTS_CORRIGES_SUR_PLACE`)."""
    source = getattr(getattr(intention, 'cible', None), 'source', '')
    statut = getattr(verrou, 'statut', '')
    if source not in SOURCES_DESIGNATIONS or statut not in STATUTS_CORRIGES_SUR_PLACE \
            or marqueur_stocke(verrou) is None:
        return False
    return statut == 'brouillon' or source == SOURCE_DESIGNATIONS_CONFIRMEES


#: Lot 8, relecture finale — la phrase de :func:`option_batterie_gardee`, vraie dans l'état.
MSG_RESYNC_OPTION_GARDEE = ('Le devis garde l’onduleur hybride « %s » et sa batterie, posés à sa création par la '
                            'désignation de l’étape Électrique : la resynchronisation ne retire ni l’un ni l’autre.')


def option_batterie_gardee(verrou, intention, lignes, veut_batterie, avertissements):
    """Lot 8, relecture finale — L'INVARIANT : une resynchronisation qui n'applique PAS les désignations
    (:func:`designations_appliquees` faux : devis envoyé, brouillon d'avant la règle, resynchro hors
    calepinage — apply-taille, brouillon libre rattaché) ne bascule JAMAIS l'option batterie d'un devis
    né « avec batterie » par un hybride désigné (D-ACAL-159) : le marqueur nomme un onduleur qu'une
    ligne d'hybride porte encore et le devis porte une batterie ⇒ ``veut_batterie`` reste vrai (aucune
    batterie retirée, aucun onduleur permuté) et la phrase est dite. Seul un brouillon né sous la règle,
    dont la désignation change, change son option. Un layout qui veut déjà une batterie, un devis sans
    marqueur ou sans onduleur désigné, un hybride changé à la main : ``veut_batterie`` inchangé, rien
    dit (résultat d'hier). ``lignes`` : les lignes produit que ``reconcilier`` vient de lire."""
    if veut_batterie or designations_appliquees(verrou, intention):
        return veut_batterie
    designe = (marqueur_stocke(verrou) or {}).get('onduleur')
    if not designe:
        return veut_batterie
    from apps.ventes.domain.catalogue import _is_battery, _is_hybrid_inverter
    from apps.ventes.domain.lignes import _classe_ligne

    hybride = next((li for li in lignes if li.produit_id == designe and _classe_ligne(li, _is_hybrid_inverter)), None)
    if hybride is None or not any(_classe_ligne(li, _is_battery) for li in lignes):
        return veut_batterie
    avertissements.append(MSG_RESYNC_OPTION_GARDEE % (hybride.designation or ''))
    return True


def appliquer_designations_a_la_resynchro(verrou, intention, layout, veut_batterie, avertissements):
    """D-ACAL-148 / 159 / 164 (relecture, A) — « Resynchroniser » applique la MÊME décision que la
    création (:func:`onduleur_designe_pour_le_devis`, :func:`juger_la_batterie`,
    :func:`batterie_designee_pour_le_devis`) ; appelée par ``resynchronisation.reconcilier`` sous son
    verrou, AVANT qu'il lise ses lignes et applique ses propres règles : il relit ce qui vient d'être
    écrit.

    Relecture, point 1 — appliquée SEULEMENT à un devis NÉ sous la règle
    (:func:`suit_les_designations`) ; ACAL1320 (D-ACAL-73) — brouillon OU envoyé
    (:data:`STATUTS_CORRIGES_SUR_PLACE` : l'envoyé est corrigé sur place, l'aperçu de la
    resynchronisation le dit avant la confirmation). Un devis créé avant (sans marqueur) : rien
    n'est appliqué (aucune écriture de plus, le court-circuit « inchangé » reste pris comme avant)
    et UNE phrase dit pourquoi.

    * chiffrable : la ligne d'onduleur de SA famille (« les deux ») ou l'unique ligne d'onduleur le
      porte, au nombre désigné, sauf une ligne CHANGÉE À LA MAIN depuis (point 2, gardée et dit une
      fois) ; un hybride sur une pose « sans » garde le devis « avec batterie » (D-ACAL-159, la
      phrase seulement quand la bascule a lieu, point 6 e) ;
    * retiré, ou plus chiffrable : la ligne qui porte encore l'ancien reprend la règle du catalogue
      (:func:`_reprendre_le_catalogue`), ou la ligne actuelle est gardée — une phrase vraie ;
    * aucune désignation, avant comme après : rien ne bouge (PV18, résultat identique à hier).

    Rend ``(veut_batterie, {'modifiees', 'a_ecrire', 'marqueur'})`` — ``a_ecrire`` interdit le
    court-circuit « inchangé » de ``reconcilier`` ; ``marqueur`` : le :data:`CLE_DESIGNATIONS` à ranger."""
    stocke = marqueur_stocke(verrou)
    cible = getattr(intention, 'cible', None)
    if not designations_appliquees(verrou, intention):
        # La phrase vraie de ce qui n'a PAS été fait (seulement quand le calepinage désigne quelque chose) :
        # devis d'avant la règle (sans marqueur) ; envoyé sans la carte d'aperçu confirmée (D-ACAL-73).
        quoi = _quoi_est_designe(cible) if getattr(cible, 'source', '') in SOURCES_DESIGNATIONS else None
        if quoi and stocke is None:
            avertissements.append(MSG_RESYNC_AVANT_LA_REGLE % quoi)
        elif quoi and getattr(verrou, 'statut', '') == 'envoye':
            avertissements.append(MSG_RESYNC_ENVOYE_SANS_APERCU % quoi)
        return _resynchro_inchangee(veut_batterie, stocke)
    from apps.ventes.domain.lignes import _lignes_produit

    precedent = stocke.get('onduleur')
    decision, scenario, phase, isole = _decision_de_resynchro(verrou, layout, cible.onduleur_impose)
    onduleurs = [li for li in _lignes_produit(verrou) if _est_onduleur(li)]
    impose = (decision or {}).get('impose')
    modifiees, main = 0, {}
    if impose:
        if decision['message'] and not _a_une_batterie(verrou):  # point 6 e — la bascule a lieu MAINTENANT
            avertissements.append(decision['message'])
        poses, main['onduleur_main'] = _poser_le_designe(verrou, impose, onduleurs, scenario, precedent, stocke,
                                                         avertissements)
        modifiees += poses
        if decision['scenario'] == COMPOSITION_AVEC and scenario == COMPOSITION_SANS:
            veut_batterie = True  # D-ACAL-159 — le devis garde « avec batterie »
    elif precedent:
        modifiees += _reprendre_le_catalogue(verrou, onduleurs, precedent, veut_batterie, layout, phase, isole,
                                             avertissements, decision=decision)
    elif decision is not None:
        actuel = next(iter(onduleurs), None)
        avertissements.append(MSG_RESYNC_NON_APPLIQUE % (
            decision['nom'], decision['raison'], ' (« %s »)' % actuel.designation if actuel is not None else ''))
    decision_b, modifiees_b, main['batterie_main'] = _batterie_a_la_resynchro(
        verrou, cible.batterie_imposee, scenario, veut_batterie, stocke, avertissements, layout=layout, phase=phase)
    marqueur = dict(marqueur_des_designations(decision, decision_b) or {},
                    **{cle: True for cle, valeur in main.items() if valeur})
    return veut_batterie, {'modifiees': modifiees + modifiees_b,
                           'a_ecrire': bool(modifiees + modifiees_b) or marqueur != stocke, 'marqueur': marqueur}


def _poser_le_designe(verrou, impose, onduleurs, scenario, precedent, stocke, avertissements):
    """La ligne d'onduleur (de SA famille dans un « les deux ») porte l'onduleur désigné ; la phrase
    dit ce qu'il remplace. Point 2 — la désignation n'a pas changé (``precedent`` = celui-ci) mais la
    ligne ne le porte plus : le vendeur l'a changé à la main, la ligne est gardée et la phrase dite
    UNE fois (``onduleur_main`` du marqueur). Rend ``(1 si une ligne a bougé, changé à la main)``."""
    from apps.ventes.domain.etape_composer import _fiche_tarifee

    produit = _fiche_tarifee(verrou.company, impose['produit_id'])
    ligne = (next((li for li in onduleurs if _famille_de_ligne(li) == impose['categorie']), None)
             if scenario == COMPOSITION_LES_DEUX else next(iter(onduleurs), None))
    if produit is None or ligne is None:
        return 0, False
    if precedent == produit.pk and ligne.produit_id != produit.pk:
        if not stocke.get('onduleur_main'):
            avertissements.append(MSG_RESYNC_CHANGE_A_LA_MAIN % (ligne.designation or '', produit.nom))
        return 0, True
    ancien = ligne.designation or ''
    if not _poser_produit(ligne, produit, impose['categorie'], avertissements, nombre=impose['nombre']):
        return 0, False
    if ancien != produit.nom:
        avertissements.append((MSG_RESYNC_CHANGE if precedent and precedent != produit.pk
                               else MSG_RESYNC_SUIT) % (produit.nom, ancien))
    return 1, False


def _hybride_de_la_resynchro(verrou, lignes, veut_batterie, scenario, layout, phase):
    """Point 5 — l'onduleur qui portera la batterie APRÈS ``reconcilier`` : celui des lignes, sinon,
    quand ``reconcilier`` va permuter le réseau en hybride (le devis veut une batterie, mono-option),
    celui qu'il posera (``catalogue.choisir_onduleur_permutation``, SA règle, mêmes entrées)."""
    from apps.ventes.domain.catalogue import (
        _is_hybrid_inverter, _is_offgrid_inverter, choisir_onduleur_permutation)
    from apps.ventes.domain.gammes import gamme_nom
    from apps.ventes.domain.lignes import _classe_ligne

    hybride = next((li.produit for li in lignes if getattr(li, 'produit', None) is not None and (
        _classe_ligne(li, _is_hybrid_inverter) or _classe_ligne(li, _is_offgrid_inverter))), None)
    if hybride is not None or not veut_batterie or scenario == COMPOSITION_LES_DEUX:
        return hybride
    return choisir_onduleur_permutation(verrou.company, _is_hybrid_inverter, kwc=_kwc_du_layout(layout)[1],
                                        phase=phase, role='onduleur_hybride', gamme=gamme_nom(verrou))


def _batterie_a_la_resynchro(verrou, brute, scenario, veut_batterie, stocke, avertissements, *, layout, phase):
    """D-ACAL-164 (A) — la batterie désignée à la resynchronisation, par :func:`batterie_designee_pour_le_devis`
    (la décision de la création), jugée sur l'onduleur qui la portera APRÈS ``reconcilier``
    (:func:`_hybride_de_la_resynchro`, point 5). Chiffrable : la ligne batterie la porte au nombre de
    packs, ou elle est créée quand le devis veut une batterie et n'en a pas ; une ligne changée à la
    main depuis est gardée (point 2). Plus appliquée : la ligne de l'ancienne au prix catalogue est
    retirée et ``reconcilier`` pose son choix automatique — seulement quand le devis veut une batterie
    (« sans » : ``reconcilier`` la retire lui-même, la phrase « sans batterie » suffit). Rend
    ``(décision, n, changée à la main)``."""
    from apps.ventes.domain.catalogue import _is_battery
    from apps.ventes.domain.composition import _est_au_prix_catalogue
    from apps.ventes.domain.lignes import _classe_ligne, _lignes_produit

    lignes = _lignes_produit(verrou)
    batteries = [li for li in lignes if _classe_ligne(li, _is_battery)]
    effectif = (COMPOSITION_LES_DEUX if scenario == COMPOSITION_LES_DEUX
                else COMPOSITION_AVEC if veut_batterie else COMPOSITION_SANS)
    hybride = _hybride_de_la_resynchro(verrou, lignes, veut_batterie, scenario, layout, phase)
    decision = (batterie_designee_pour_le_devis(verrou.company, brute, scenario=effectif, hybride=hybride)
                if brute else None)
    impose = (decision or {}).get('impose')
    precedent = stocke.get('batterie')
    if impose:
        if decision['message']:
            avertissements.append(decision['message'])
        n, main = _poser_la_batterie(verrou, impose, batteries, veut_batterie, effectif, precedent, stocke,
                                     avertissements)
        return decision, n, main
    if decision is not None and decision['motif'] == 'sans':
        avertissements.append(decision['message'])
        return decision, 0, False
    ancienne = next((li for li in batteries if li.produit_id == precedent), None) if precedent else None
    if ancienne is None or effectif == COMPOSITION_SANS:
        if decision is not None:
            avertissements.append(MSG_RESYNC_BATTERIE_NON_APPLIQUEE % (decision['nom'], decision['raison'], (
                'le devis garde sa batterie actuelle' if batteries else 'la batterie suit la règle automatique')))
        return decision, 0, False
    if not _est_au_prix_catalogue(ancienne) or getattr(ancienne, 'quantite_manuelle', False):
        avertissements.append((MSG_RESYNC_QUANTITE_MANUELLE % (ancienne.designation or 'ligne sans désignation'))
                              if _est_au_prix_catalogue(ancienne) else MSG_RESYNC_PRIX_MANUEL % (
                                  ancienne.designation or 'ligne sans désignation', 'le choix automatique'))
        return decision, 0, False
    avertissements.append(MSG_RESYNC_BATTERIE_NON_CHIFFREE_REPRISE % (decision['nom'], decision['raison'])
                          if decision is not None else MSG_RESYNC_BATTERIE_RETIREE % (ancienne.designation or ''))
    ancienne.delete()
    return decision, 1, False


def _poser_la_batterie(verrou, impose, batteries, veut_batterie, scenario, precedent, stocke, avertissements):
    from apps.ventes.domain.etape_composer import _fiche_tarifee
    from apps.ventes.domain.lignes import creer_ligne
    from apps.ventes.domain.resynchronisation import _ordre_suivant

    produit = _fiche_tarifee(verrou.company, impose['produit_id'])
    if produit is None:
        return 0, False
    ligne = next(iter(batteries), None)
    if ligne is not None and precedent == produit.pk and ligne.produit_id != produit.pk:
        if not stocke.get('batterie_main'):  # point 2 — changée à la main depuis : gardée, dit une fois
            avertissements.append(MSG_RESYNC_BATTERIE_A_LA_MAIN % (ligne.designation or '', produit.nom))
        return 0, True
    if ligne is None:
        if not veut_batterie:
            return 0, False
        creer_ligne(verrou, produit=produit, designation=produit.nom, quantite=Decimal(impose['nombre']),
                    prix_unitaire=Decimal(produit.prix_vente), remise=Decimal('0'), ordre=_ordre_suivant(verrou),
                    **({'variante': 'avec'} if scenario == COMPOSITION_LES_DEUX else {}))
    elif not _poser_produit(ligne, produit, 'batterie', avertissements, nombre=impose['nombre']):
        return 0, False
    avertissements.append(MSG_RESYNC_BATTERIE_SUIT % (produit.nom, impose['nombre']))
    return 1, False


def build_devis_from_layout(*, layout, user, company, lead=None, client=None,
                            taux_tva=None, remise_globale=Decimal('0'),
                            deux_options=False, journal=None, phase=None,
                            dimensionnement_avec=None,
                            mppt_paires=1, structure_type=None,
                            structure_produit_id=None, hors_reseau=None, a_blanc=False,
                            onduleur_designe=None, batterie_designee=None, marquer_designations=False):
    """Q3 — turn a FINALISED roof layout into a coherent, company-scoped Devis.

    ``onduleur_designe`` (D-ACAL-148, fondateur 26/11/2026) — l'onduleur DÉSIGNÉ à l'étape
    Électrique du calepinage, ``{'produit_id', 'nombre'}`` : le devis le chiffre quand il est au
    catalogue avec un prix et que la forme du devis peut le porter
    (:func:`decision_onduleur_designe`), sinon il garde l'onduleur de la composition et le DIT
    (``journal['avertissements']``). ``journal['onduleur_designe']`` reçoit la décision (aussi
    à blanc : l'aperçu la lit). ``None`` (LE DÉFAUT) ⇒ composition inchangée.

    ``batterie_designee`` (D-ACAL-164) — la batterie DÉSIGNÉE à l'étape Électrique,
    ``{'produit_id', 'packs', 'packs_illisible'}`` : vendue au nombre de packs quand elle a un prix et
    convient à l'onduleur du devis (:func:`decision_batterie_designee`), sinon le choix automatique,
    dit ; ``journal['batterie_designee']``. ``None`` ⇒ inchangé. ``marquer_designations`` (la
    génération du calepinage) : le marqueur privé est posé même sans désignation (né sous la règle).

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
    # D-ACAL-149 (ii) — la création fait toujours un brouillon (ouvert) : lecture corrigée.
    lecture = lire_layout(layout, toit_plat_corrige=True)
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
                              compte=nb_panneaux, kwc=kwc, toit_plat_corrige=True)
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
        # D-ACAL-159 — l'hybride désigné d'un devis « sans » le fait passer « avec ».
        scenario=(designe['scenario'] if designe is not None and designe['impose'] else scenario),
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
    # D-ACAL-148 / 159 / 164 — batterie désignée, batterie de l'onduleur, marqueur, journal, phrases.
    intention, annonces = _appliquer_les_designations(intention, designe, batterie_designee, scenario, journal,
                                                      marquer=marquer_designations)
    suppositions = phrases_des_suppositions(toiture)  # D-ACAL-149 (ii) / 168 — dites au vendeur
    annonces += suppositions
    if journal is not None and suppositions:  # la même phrase à l'aperçu (round 4)
        journal['suppositions_toit'] = suppositions
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
    scenario_du_layout,
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
