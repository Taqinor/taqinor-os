"""Option « AVEC BATTERIE » d'une étude / d'un devis C&I — côté orchestrateur
(décision fondateur du 26/10/2026 : un devis commercial / industriel porte deux
options, « sans » et « avec batterie », comme le résidentiel).

Le calcul vit dans ``moteur_ci.batterie`` (pur) ; ce module lit le catalogue
de la société (par les sélecteurs ``stock`` — jamais ses modèles), résout le
choix du lead, construit les fermetures (combinaison d'hybrides, composition,
valorisation) et met l'option à la forme servie par l'étude
(``etude['option_avec']``).

Identification par FICHE et par RÔLE, jamais par le nom seul :

* hybride C&I = rôle ``onduleur_hybride`` (déclaré, sinon catégorie, sinon
  mots-clés — ``core.product_roles.role_effectif``) ET fiche onduleur dont la
  plage batterie déclarée est BASSE TENSION (≤ 60 V : Deye SG05LP3) — un
  hybride haute tension (SG02HP3, 160–700 V) n'y entre jamais ;
* batterie C&I = rôle ``batterie_ci`` (C&I) ou ``batterie`` ET fiche batterie
  publiant sa capacité UTILE (``kwh_usable``, sinon nominal × DoD) et une
  tension nominale dans la plage des hybrides — sans fiche, la batterie est
  écartée et NOMMÉE (alerte interne), jamais lue dans son nom.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Choix du lead / du corps (``Lead.batterie_souhaitee``, même champ que le
#: résidentiel). Silence ⇒ les deux options (U2).
CHOIX = ('sans', 'avec', 'les_deux')
LES_DEUX = 'les_deux'
CLE = 'option_avec'


def choix_batterie(valeur, lead=None):
    """``'sans'`` / ``'avec'`` / ``'les_deux'`` : la valeur explicite du corps,
    sinon ``lead.batterie_souhaitee``, sinon les deux. Un booléen (case
    « batterie souhaitée » de l'aperçu) ne restreint rien."""
    for candidat in (valeur, getattr(lead, 'batterie_souhaitee', None)):
        if isinstance(candidat, str) and candidat.strip().lower() in CHOIX:
            return candidat.strip().lower()
    return LES_DEUX


def _num(valeur):
    try:
        return float(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def _role(produit):
    from core.product_roles import role_effectif

    from .catalogue import classer_produit
    categorie = getattr(produit, 'categorie', None)
    return role_effectif(getattr(produit, 'role_devis', None),
                         getattr(categorie, 'type_equipement', None),
                         getattr(produit, 'nom', ''), classer_produit)[0]


def designation_option_avec(nom, role_devis):
    """La désignation de LIGNE d'un article de l'option « avec » : le nom du
    catalogue, précédé de sa famille quand il ne la dit pas (« SUN-12K-SG05LP3 »
    → « Onduleur hybride SUN-12K-SG05LP3 ») — le découpage des deux options du
    document lit ces mots (``solar_classification``), le rôle les prouve."""
    from apps.ventes.solar_classification import is_battery, is_hybrid_inverter
    nom = (nom or '').strip()
    if role_devis == 'onduleur_hybride' and not is_hybrid_inverter(nom):
        return 'Onduleur hybride %s' % nom
    if role_devis == 'batterie' and not is_battery(nom):
        return 'Batterie %s' % nom
    return nom


def _element(produit, role_devis, fiche):
    """L'article à la forme des éléments ``produits_ci`` (composition)."""
    prix = produit.prix_vente if produit.prix_vente and produit.prix_vente > 0 else None
    element = {'id': produit.id, 'nom': designation_option_avec(produit.nom, role_devis),
               'marque': produit.marque or '',
               'role_devis': role_devis, 'role_ci': getattr(produit, 'role_ci', '') or '',
               'type_pose': '', 'fiche': fiche, 'prix_connu': prix is not None,
               'eligible_ci': True, 'motif_exclusion': None}
    if prix is not None:
        element.update(prix_vente_ht=prix, tva_pct=getattr(produit, 'tva', None),
                       paliers_prix_vente=list(getattr(produit, 'paliers_prix_vente', None) or []))
    return element


def _hybride(produit, specs, plage, triphase):
    from apps.calepinage.services.chaines import specs_onduleur
    prix = produit.prix_vente if produit.prix_vente and produit.prix_vente > 0 else None
    return {
        'produit': produit.id, 'nom': produit.nom, 'kw_ac': specs.get('ac_kw'), 'prix': prix,
        'triphase': triphase, 'phases': specs.get('phases'), 'eligible_ci': True,
        'motif_exclusion': None, 'dc_max_kwc': specs.get('dc_max_kwc'),
        'chaines_max_par_mppt': specs.get('chaines_max_par_mppt'),
        's_max_kva': specs.get('s_max_kva'), 'plage_batterie_v': list(plage),
        'bat_max_charge_kw': specs.get('bat_max_charge_kw'),
        'bat_max_decharge_kw': specs.get('bat_max_decharge_kw'),
        'spec': specs_onduleur(specs, produit.nom)[0] if specs else None,
    }


def _capacite_utile(specs):
    utile = _num(specs.get('kwh_usable'))
    if utile:
        return utile
    nominal, dod = _num(specs.get('kwh_nominal')), _num(specs.get('dod_pct'))
    return nominal * dod / 100.0 if nominal and dod else None


def _batterie(produit, specs):
    from apps.ventes.quote_engine.pricing import BATTERY_ROUNDTRIP
    rendement = _num(specs.get('rendement_ar_pct'))
    return {
        'produit': produit.id, 'nom': produit.nom, 'kwh_utile': _capacite_utile(specs),
        'v_nominal': _num(specs.get('v_nominal')),
        'prix': produit.prix_vente if produit.prix_vente and produit.prix_vente > 0 else None,
        'max_modules': specs.get('max_modules_par_banc'),
        'max_charge_kw': _num(specs.get('max_charge_kw')),
        'max_decharge_kw': _num(specs.get('max_decharge_kw')),
        'rendement': rendement / 100.0 if rendement and 0 < rendement <= 100
        else BATTERY_ROUNDTRIP,
        # CMP6 — année de remplacement du flux 25 ans (fiche, sinon défaut étiqueté).
        'garantie_mois': getattr(produit, 'garantie_mois', None),
        'cycles_publies': _num(specs.get('cycles_publies')),
        'element': _element(produit, 'batterie', {}),
    }


def catalogue_batterie_ci(objets):
    """``{hybrides, batteries, elements, ecartees}`` du catalogue de la
    société (objets ``catalogue_de_la_societe``) — lecture seule."""
    from apps.stock.selectors import plage_batterie_onduleur, specs_for_produit
    from apps.ventes.moteur_ci.batterie import TENSION_PORT_BT_MAX_V

    from ..compatibilites import est_triphase_produit
    hybrides, batteries, elements, ecartees = [], [], [], []
    for produit in objets:
        role = _role(produit)
        fiche = getattr(produit, 'fiche_technique', None)
        type_fiche = getattr(fiche, 'type_fiche', None)
        if role == 'onduleur_hybride' and type_fiche == 'onduleur':
            plage = plage_batterie_onduleur(produit)
            if not plage or not 0 < plage[1] <= TENSION_PORT_BT_MAX_V:
                continue          # hybride haute tension (ou plage non déclarée)
            specs = specs_for_produit(produit) or {}
            hybrides.append(_hybride(produit, specs, plage, est_triphase_produit(produit)))
            elements.append(_element(produit, 'onduleur_hybride', {
                'ond_phases': specs.get('phases'), 'ond_n_mppt': specs.get('n_mppt'),
                'ond_ac_kw': specs.get('ac_kw')}))
        elif role == 'batterie' or getattr(produit, 'role_ci', '') == 'batterie_ci':
            specs = (specs_for_produit(produit) or {}) if type_fiche == 'batterie' else {}
            batterie = _batterie(produit, specs)
            if not batterie['kwh_utile'] or batterie['v_nominal'] is None:
                ecartees.append(produit.nom)
                continue
            batteries.append(batterie)
    return {'hybrides': hybrides, 'batteries': batteries, 'elements': elements,
            'ecartees': ecartees}


def batteries_compatibles(batteries, hybrides):
    """Les batteries dont la tension nominale entre dans la plage d'AU MOINS
    un hybride retenu (règle PVOND : la tension mesurée prouve l'appairage)."""
    plages = [h['plage_batterie_v'] for h in hybrides or [] if h.get('plage_batterie_v')]
    return [b for b in batteries or []
            if any(bas <= b['v_nominal'] <= haut for bas, haut in plages)]


def _nb_panneaux(composition):
    return next((ligne.get('quantite') for ligne in (composition or {}).get('lignes') or []
                 if ligne.get('role') == 'panneau'), None)


def _ligne_flux(designation, ht, ttc, *, onduleur=False, role_ci=''):
    """Une ligne à la forme ``economie_ci.onduleur_et_om`` (totaux CLIENT)."""
    return {'designation': designation, 'ht': ht, 'ttc': ttc,
            'optionnelle': False, 'onduleur': onduleur, 'role_ci': role_ci}


def _investissement_composition(evaluation, taux_tva_pct, regles_2710=True):
    """CMP6 — ``{ht, ttc, lignes}`` de l'option « avec » composée : le HT est
    ``evaluation['cout']`` (le coût de vente servi) ; le TTC, la somme des
    lignes à la TVA de LEUR article (``tva_pct``), à défaut au taux standard
    de la société. ``None`` quand la composition est incomplète (prix à
    renseigner / à chiffrer après la visite : ADEV81 — jamais un retour sur un
    total qui n'est pas celui de l'installation) ou sans coût. Jamais
    ``prix_achat``. ``regles_2710`` faux (devis envoyé au niveau ≤ 2) : l'O&M
    reste dans l'année 0, comme avant CEC1."""
    from apps.ventes.moteur_ci.composition import prix_palier_ht
    composition, cout = evaluation.get('composition'), evaluation.get('cout')
    if not composition or composition.get('incomplet') or not cout or cout <= 0:
        return None
    taux_defaut = _num(taux_tva_pct)
    from core.money import quantize_mad

    def _mad(x):
        return float(quantize_mad(str(x)))

    lignes, ttc_total, ttc_connu = [], 0.0, True

    def ttc_de(ht, taux):
        nonlocal ttc_total, ttc_connu
        taux = _num(taux)
        taux = taux_defaut if taux is None else taux
        if taux is None:
            # Sans TVA connue : la ligne reste comptée (TTC = HT) pour que
            # ``economie_ci._somme_lignes`` ne la retire pas (le remplacement de
            # l'onduleur disparaîtrait) ; le TTC de l'investissement reste None.
            ttc_connu = False
            return _mad(ht)
        ttc_total += ht * (1 + taux / 100.0)
        return _mad(ht * (1 + taux / 100.0))

    onduleurs = evaluation.get('onduleurs') or {}
    if _num(onduleurs.get('prix_vente_total_ht')):
        ht = float(onduleurs['prix_vente_total_ht'])
        lignes.append(_ligne_flux('Onduleur(s) hybride(s)', _mad(ht),
                                  ttc_de(ht, None), onduleur=True))
    for ligne in composition.get('lignes') or []:
        if ligne.get('role') == 'onduleur_string_tri' or ligne.get('a_chiffrer_visite') \
                or not ligne.get('prix_connu'):
            continue
        quantite = _num(ligne.get('quantite'))
        unitaire = prix_palier_ht(ligne, taux_tva_pct)
        unitaire = _num(ligne.get('prix_unitaire_ht')) if unitaire is None else float(unitaire)
        if not quantite or unitaire is None:
            continue
        ht = quantite * unitaire
        nom = str(ligne.get('designation') or '')
        if ligne.get('role') == 'batterie_ci' and 'batterie' not in nom.lower():
            nom = 'Batterie ' + nom
        lignes.append(_ligne_flux(
            nom, _mad(ht), ttc_de(ht, ligne.get('tva_pct')),
            role_ci='om_ci' if ligne.get('role') == 'om_ci' else ''))
    from apps.ventes.economie_ci_options import investissement_hors_om
    investissement = investissement_hors_om(
        {'ht': float(cout), 'ttc': _mad(ttc_total) if ttc_connu else None}, lignes, regles_2710)
    return dict(investissement, lignes=lignes)


def _flux_option_avec(evaluation, economie, investissement, ctx):
    """CMP6 — le flux 25 ans de l'option « avec » par ``flux_option_avec``
    (CEC3) : MÊMES conventions que l'option « sans »
    (``economie_ci.assembler_economie_ci``) — base HT / TTC / les deux selon
    la TVA récupérable déclarée (D-CIQ-3 ; non fournie ⇒ « inconnu » ⇒ les
    deux bases, la principale étant le HT), économie an 1 = le bloc complet du
    valoriseur, production du bilan, kWh évités par poste. ``None`` dès qu'une
    entrée manque (économie omise, investissement non chiffré) — jamais le
    quotient coût ÷ économie."""
    from apps.ventes import economie_ci as eco
    from apps.ventes.economie_ci_options import (
        annee_remplacement_batterie, flux_option_avec,
    )
    annee1 = economie.get('economie_annee1') if isinstance(economie, dict) else None
    if not investissement or not isinstance(annee1, dict) \
            or economie.get('statut') == eco.STATUT_OMIS \
            or not _num(annee1.get('total_mad')):
        return None
    base = eco.base_economique(
        ctx.get('tva_recuperable'),
        investissement={'ht': investissement['ht'], 'ttc': investissement['ttc']},
        economie_annee1=annee1)
    fiche = ctx.get('batterie') or {}
    kwh = sum(_num(p.get('kwh_evites')) or 0.0 for p in annee1.get('par_poste') or [])
    return flux_option_avec(
        base, lignes=investissement['lignes'],
        batterie=annee_remplacement_batterie(fiche.get('garantie_mois'),
                                             fiche.get('cycles_publies')),
        production_annee1_kwh=_num((evaluation.get('bilan') or {}).get('production_kwh')),
        kwh_evites_an=kwh, **(ctx.get('flux') or {}))


def _bloc(evaluation, valoriser=None, ctx=None, investissement=None):
    """La forme servie ``etude['option_avec']`` (jamais ``prix_achat``) : le
    bilan SANS sa ventilation horaire (le PDF et l'écran lisent les totaux),
    l'``economie_ci`` complète quand le valoriseur la sert (document à option
    « avec » seule), le coût de vente HT quand la composition est connue
    (étude ; le rafraîchisseur lit les totaux des lignes).

    CMP6 — ``retour_simple_ans`` = le retour lu sur le flux 25 ans
    (``economie_ci_options.flux_option_avec`` : dégradation, remplacement des
    onduleurs et de la batterie, entretien), le MÊME moteur que l'option
    « sans » ; ``economie_flux`` porte tout le flux. ``None`` quand une entrée
    manque. ``ctx`` : ``{tva_recuperable, taux_tva_pct, batterie, flux,
    regles_2710}``.
    ``investissement`` : ``{ht, ttc, lignes}`` imposé (option des lignes du
    devis) ; sinon celui de la composition."""
    from .etude_ci import _forme_composition

    from core.money import quantize_mad
    ctx = ctx or {}
    economie, cout = evaluation.get('economie'), evaluation.get('cout')
    complet = getattr(valoriser, 'complet', None)
    economie_ci = complet(evaluation['bilan']) if complet else None
    flux = None
    if complet:
        if investissement is None:
            investissement = _investissement_composition(
                evaluation, ctx.get('taux_tva_pct'), ctx.get('regles_2710', True))
        flux = _flux_option_avec(evaluation, economie_ci, investissement, ctx)
    return {
        'kwc': evaluation['kwc'], 'nb_panneaux': _nb_panneaux(evaluation.get('composition')),
        'puissance_ac_kw': evaluation.get('puissance_ac'),
        'batterie': evaluation['batterie'],
        # Les seules clés servables d'un appareil (jamais sa fiche SpecOnduleur).
        'onduleurs': {'combinaison': [
            {k: item.get(k) for k in ('produit', 'nom', 'kw_ac', 's_max_kva', 'quantite')}
            for item in (evaluation.get('onduleurs') or {}).get('combinaison') or []],
            'ratio_dc_ac': (evaluation.get('onduleurs') or {}).get('ratio_dc_ac')},
        'composition': _forme_composition(evaluation.get('composition')),
        'bilan': {k: v for k, v in (evaluation.get('bilan') or {}).items() if k != 'horaire'},
        'economie_ci': economie_ci,
        'economie_annuelle_mad': None if economie is None else round(economie, 2),
        'cout_vente_ht': None if cout is None else float(quantize_mad(str(cout))),
        'retour_simple_ans': ((flux or {}).get('indicateurs') or {}).get('retour_dixieme_ans'),
        'economie_flux': flux,
    }


def _alerte(code, message, niveau='alerte'):
    return {'code': code, 'champ': 'option_avec', 'message': message,
            'niveau': niveau, 'interne': True}


def _option_dominee(sans, avec):
    """CMP9 (D-CMP-5) — l'option « avec » coûte AU MOINS autant ET économise AU
    PLUS autant que « sans » : dominée. Un coût ou une économie manquant d'un
    côté ⇒ aucun verdict."""
    valeurs = [(e or {}).get(cle) for e in (sans, avec) for cle in ('cout', 'economie')]
    if any(v is None for v in valeurs):
        return False
    return avec['cout'] >= sans['cout'] and avec['economie'] <= sans['economie']


def _alerte_dominee(sans, avec, alertes, choix):
    codes = {a.get('code') for a in alertes}
    cause = ' ; '.join(texte for code, texte in (
        ('HYBRIDES_PARALLELE_MAX', 'borne de hybrides en parallèle'),
        ('BATTERIE_REDUITE_AU_TOIT', 'banque réduite au toit')) if code in codes)
    return _alerte('OPTION_BATTERIE_DOMINEE', (
        'Option « avec batterie » non proposée : plus chère (%.0f contre %.0f HT) et '
        'économie annuelle plus faible (%.0f contre %.0f MAD)%s.'
        % (avec['cout'], sans['cout'], avec['economie'], sans['economie'],
           ' — cause : %s' % cause if cause else '')),
        niveau='bloquant' if choix == 'avec' else 'alerte')


def _dimensionner(catalogue, bat, batteries, evaluation, *, phase, ps_kva, composer,
                  borne_toit, production_rasante=None, **noyau):
    from apps.ventes.etude_horaire import simuler_batterie_jour
    from apps.ventes.moteur_ci.batterie import (
        MAX_HYBRIDES_PARALLELE, dimensionner_option_avec,
    )
    from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
    from apps.ventes.moteur_ci.taille import inclinaison_pose
    # R1 (P2, arbitrage coordinatrice 28/10/2026) — la règle (1)→(3) vaut
    # pour CHAQUE option : le champ « avec » est évalué dans la pose qui le
    # loge (30° tant qu'il tient, rasante au-delà), borné par la contenance
    # maximale ; chaque option est une installation à part.
    production_de, bornes_pub = _production_de_la_pose(borne_toit, production_rasante,
                                                       noyau['production'])
    resultat = dimensionner_option_avec(
        simuler=simuler_batterie_jour,
        kwc_depart=evaluation['kwc'], pmax_wc=(catalogue.get('module') or {}).get('pmax_wc'),
        combiner=lambda kwc: combiner_onduleurs(
            kwc, bat['hybrides'], phase=phase, module=catalogue.get('module_spec'),
            ac_max_kw=ps_kva, max_appareils=MAX_HYBRIDES_PARALLELE, homogene=True),
        composer=lambda kwc, onduleurs: composer(kwc, onduleurs, bat.get('elements')),
        batteries=batteries, hybrides=bat['hybrides'], kwc_max=(borne_toit or {}).get('kwc'),
        ps_kva=ps_kva, production_de=production_de,
        # Fondateur 30/10/2026 — l'option « sans » est le point n = 0 de la
        # règle marginale des 7 ans sur la banque (coût de vente HT, économie).
        cout_depart=evaluation.get('cout'), economie_depart=evaluation.get('economie'),
        **noyau)
    if resultat.get('evaluation'):
        resultat['evaluation']['inclinaison_retenue_deg'] = inclinaison_pose(
            resultat['evaluation']['kwc'], bornes_pub)
    return resultat


def _production_de_la_pose(borne_toit, production_rasante, production_30):
    """R1 — ``(production_de(kwc), bornes)`` : la production de la pose qui
    loge ``kwc`` — 30° tant qu'il tient (``kwc_30``), rasante au-delà
    (``production_rasante()``, série 10°) ; sans les deux contenances ou sans
    série rasante, la production de l'option « sans »."""
    from apps.ventes.moteur_ci.taille import contenances_toit, pose_rasante
    bornes_pub = {'toit': borne_toit}
    kwc_30, kwc_10 = contenances_toit(bornes_pub)

    def production_de(kwc):
        if production_rasante is not None and pose_rasante(kwc, kwc_30, kwc_10):
            return production_rasante() or production_30
        return production_30
    return production_de, bornes_pub


def _fusion_variantee(sans, avec):
    """Les lignes des deux options en UNE liste variantée, par LA fusion du
    résidentiel (``composition.fusionner_kits``, L-2OPT) : une ligne identique
    des deux côtés (article, désignation, quantité, prix) est commune, les
    autres portent ``variante`` « sans » / « avec », côte à côte."""
    from types import SimpleNamespace

    from .composition import LigneKit, fusionner_kits

    def kit(lignes):
        return [(ligne['produit_id'], LigneKit(
            SimpleNamespace(pk=ligne['produit_id']), ligne['designation'],
            ligne['quantite'], ligne['prix_unitaire'])) for ligne in lignes]

    return [{'produit_id': ligne.produit.pk, 'designation': ligne.designation,
             'quantite': ligne.quantite, 'prix_unitaire': ligne.prix_unitaire,
             'variante': ligne.variante}
            for _role, ligne in fusionner_kits(kit(sans), kit(avec))]


def lignes_des_options(etude, lead=None):
    """``(lignes, scénario)`` du devis automatique C&I (fondateur 26/10/2026,
    comme le résidentiel U2) : sans option « avec » composée, les lignes de
    l'option « sans » seules (scénario ``None`` : inchangé) ; choix « avec »
    du lead ⇒ les lignes « avec » seules ; sinon LES DEUX, variantées."""
    from .etude_ci import lignes_du_devis_ci
    from .scenario import SCENARIO_AVEC_BATTERIE, SCENARIO_LES_DEUX
    sans = lignes_du_devis_ci(etude.get('composition'))
    bloc = etude.get(CLE)
    if not bloc:
        return sans, None
    avec = lignes_du_devis_ci(bloc.get('composition'))
    choix = ((etude.get('entrees_resolues') or {}).get('batterie_souhaitee') or {}).get('valeur')
    if choix_batterie(choix, lead) == 'avec':
        return avec, SCENARIO_AVEC_BATTERIE
    return _fusion_variantee(sans, avec), SCENARIO_LES_DEUX


def _investissement_des_lignes(lignes, devis=None):
    """CMP6 — ``{ht, ttc, lignes}`` de l'option « avec » des LIGNES du devis,
    lu comme l'économie de l'option « sans » (``economie_ci_pour_devis``) :
    totaux NETS de ``utils.options.option_totaux`` (remise de ligne ET remise
    globale), lignes de ``economie_ci.lignes_pour_economie_ci``, O&M retirée de
    l'année 0 (``investissement_hors_om``, CEC1). ``devis`` : à défaut, celui
    des lignes. ``None`` quand l'option que suit l'argent du devis n'est pas
    l'option « avec » (devis accepté « sans »), sans devis, ou sans total."""
    from apps.ventes import economie_ci as eco
    from apps.ventes.domain.regles_calcul import REGLES_CORRIGEES_2710, regles_au_moins
    from apps.ventes.economie_ci_options import investissement_hors_om
    from apps.ventes.utils.options import AVEC_BATTERIE, option_effective, option_totaux
    devis = devis or next((d for d in (getattr(li, 'devis', None) for li in lignes or [])
                           if d is not None), None)
    if devis is None or option_effective(devis) not in ('', AVEC_BATTERIE):
        return None
    totaux = option_totaux(devis)
    ht, ttc = _num(totaux.get('ht')), _num(totaux.get('ttc'))
    detail = eco.lignes_pour_economie_ci(devis)
    if not ht or ht <= 0 or not detail:
        return None
    # CEC1 est une règle du 27/10 : un devis envoyé avant (niveau ≤ 2) garde son O&M en an 0.
    investissement = investissement_hors_om(
        {'ht': ht, 'ttc': ttc}, detail, regles_au_moins(devis, REGLES_CORRIGEES_2710))
    return {'ht': investissement['ht'], 'ttc': investissement['ttc'], 'lignes': detail}


def option_imposee_des_lignes(lignes, catalogue, kwc, nb_panneaux=None, devis=None):
    """CIQ119 — l'option « avec » telle que les LIGNES du devis la portent :
    ``{kwc, onduleurs, banque, hybrides, nb_panneaux, empreinte}`` — les
    hybrides basse tension et les batteries du catalogue C&I présents sur les
    lignes de l'option « avec » (variante ``avec`` ou commune), ou ``None``
    quand il manque l'un ou l'autre. Une banque de modèles mêlés (saisie du
    vendeur) est lue à sa capacité utile totale."""
    bat = catalogue.get('batterie') or {}
    hybrides = {h['produit']: h for h in bat.get('hybrides') or []}
    batteries = {b['produit']: b for b in bat.get('batteries') or []}
    q_h, q_b = {}, {}
    for ligne in lignes or []:
        if getattr(ligne, 'type_ligne', 'produit') != 'produit' \
                or getattr(ligne, 'optionnelle', False) \
                or (getattr(ligne, 'variante', '') or '') == 'sans':
            continue
        pid, quantite = getattr(ligne, 'produit_id', None), int(getattr(ligne, 'quantite', 0) or 0)
        cible = q_h if pid in hybrides else q_b if pid in batteries else None
        if cible is not None and quantite > 0:
            cible[pid] = cible.get(pid, 0) + quantite
    if not q_h or not q_b or not kwc:
        return None
    total = sum(q_b.values())
    capacite = sum(batteries[p]['kwh_utile'] * q for p, q in q_b.items())
    banque = dict(batteries[max(sorted(q_b), key=q_b.get)], quantite=total,
                  kwh_utile=capacite / total)
    return {'kwc': kwc, 'nb_panneaux': nb_panneaux, 'banque': banque,
            'investissement': _investissement_des_lignes(lignes, devis),
            'onduleurs': {'combinaison': [dict(hybrides[p], quantite=q) for p, q in sorted(q_h.items())]},
            'hybrides': list(hybrides.values()),
            'empreinte': [kwc, sorted(q_h.items()), sorted(q_b.items())]}


def _ctx_flux(contexte, batterie):
    """CMP6 — le contexte du flux 25 ans de l'option « avec » : TVA
    récupérable résolue (D-CIQ-3), taux standard, fiche de la batterie
    (garantie / cycles), réglages de ``flux_ci`` (``degradation``,
    ``entretien``, ``taux_actualisation_client``) et niveau de règles du devis
    (``regles_2710`` : CEC1, O&M hors de l'année 0, seulement au niveau 3)."""
    return {'tva_recuperable': contexte.get('tva_recuperable'),
            'taux_tva_pct': contexte.get('taux_tva_pct'),
            'regles_2710': contexte.get('regles_2710', True),
            'flux': contexte.get('flux_options') or {}, 'batterie': batterie}


def _recomposer(catalogue, imposee, contexte):
    """CORC10 — l'option « avec » des lignes RECOMPOSÉE à sa taille vendue
    (kWc et banque des lignes, jamais redimensionnés) : hybrides recombinés à
    ce kWc et composition avec les entrées de l'étude (mesures de visite)."""
    from apps.ventes.moteur_ci.batterie import MAX_HYBRIDES_PARALLELE, _composer_avec
    from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
    bat = catalogue.get('batterie') or {}
    onduleurs = combiner_onduleurs(
        imposee['kwc'], bat.get('hybrides') or [], phase=contexte.get('phase'),
        module=catalogue.get('module_spec'), ac_max_kw=contexte.get('ps_kva'),
        max_appareils=MAX_HYBRIDES_PARALLELE, homogene=True) or {}
    composition = _composer_avec(
        lambda kwc, ond: contexte['composer'](kwc, ond, bat.get('elements')),
        imposee['kwc'], onduleurs, imposee['banque'])
    return dict(imposee, onduleurs=onduleurs, composition=composition, investissement=None)


def _option_imposee(imposee, contexte):
    """Le bilan et l'économie de l'option « avec » des lignes (aucun
    redimensionnement ; sans ``composition`` recomposée — CORC10 — le coût
    est celui des lignes)."""
    from apps.ventes.etude_horaire import simuler_batterie_jour
    from apps.ventes.moteur_ci.batterie import evaluer_option_avec
    from apps.ventes.moteur_ci.taille import inclinaison_pose
    # R1 (B2) — l'option des LIGNES est évaluée dans la pose qui LA loge (série
    # rasante figée au-delà de 30°), jamais avec la production de l'option « sans ».
    production_de, bornes_pub = _production_de_la_pose(
        contexte.get('borne_toit'), contexte.get('production_rasante'), contexte['production'])
    evaluation = evaluer_option_avec(
        # CORC10 : la composition RECOMPOSÉE des lignes (coût) ; R1 (B2) : la
        # production de la pose qui loge ce champ.
        imposee['kwc'], imposee['onduleurs'], imposee.get('composition'), imposee['banque'],
        charge=contexte['charge'], production=production_de(imposee['kwc']),
        tension=contexte['tension'], revente_choisie=contexte['revente_choisie'],
        valoriser=contexte['valoriser'], simuler=simuler_batterie_jour,
        hybrides=imposee['hybrides'], taux_tva_pct=contexte.get('taux_tva_pct'))
    bloc = _bloc(evaluation, contexte['valoriser'], _ctx_flux(contexte, imposee['banque']),
                 investissement=imposee.get('investissement'))
    bloc['nb_panneaux'] = imposee.get('nb_panneaux') or bloc['nb_panneaux']
    angle = inclinaison_pose(imposee['kwc'], bornes_pub)
    if angle is not None:
        bloc['inclinaison_retenue_deg'] = angle      # clé ADDITIVE, comme à l'étude
    return bloc


def option_avec_de_l_etude(catalogue, evaluation, *, choix, lead, imposee=None, **contexte):
    """``{bloc, prix_a_renseigner, alertes, hypotheses}`` de l'option « avec
    batterie » d'une étude C&I dont l'option « sans » est ``evaluation``.
    ``contexte`` : ``charge, production, tension, revente_choisie, valoriser,
    taux_tva_pct`` (noyau) + ``phase, ps_kva, composer, borne_toit`` +
    ``production_rasante`` (R1 : appelable paresseux de la production en pose
    rasante, ou ``None``) + ``regles_2710`` (``regles_au_moins(devis,
    REGLES_CORRIGEES_2710)`` ; absent ⇒ règles courantes).
    ``imposee`` (rafraîchisseur CIQ119) : l'option des LIGNES
    (:func:`option_imposee_des_lignes`), évaluée telle quelle.
    Choix « sans » ⇒ rien ; choix « avec » non composable ⇒ alerte BLOQUANTE
    (refus nommé) ; « les deux » non composable ⇒ alerte interne, l'option
    « sans » reste seule."""
    vide = {'bloc': None, 'prix_a_renseigner': [], 'alertes': [], 'hypotheses': []}
    # CMP6 — entrées du flux 25 ans, hors noyau du dimensionnement.
    flux = {cle: contexte.pop(cle, None) for cle in ('tva_recuperable', 'flux_options')}
    flux['taux_tva_pct'] = contexte.get('taux_tva_pct')
    flux['regles_2710'] = contexte.pop('regles_2710', True)
    production_rasante = contexte.pop('production_rasante', None)
    flux['production_rasante'] = production_rasante
    if flux['tva_recuperable'] is None:
        # D-CIQ-3 : la MÊME résolution que l'économie de l'option « sans »
        # (le lead d'abord ; rien de déclaré ⇒ « inconnu », les deux bases).
        from apps.ventes.economie_ci import resoudre_tva_recuperable
        flux['tva_recuperable'] = resoudre_tva_recuperable(
            getattr(lead, 'tva_recuperable', None))
    if imposee is not None and imposee.get('recomposer'):
        imposee = _recomposer(catalogue, imposee, contexte)
        return dict(vide, bloc=_option_imposee(imposee, dict(contexte, **flux)),
                    prix_a_renseigner=list(imposee['composition'].get('prix_a_renseigner') or []))
    if imposee is not None:
        return dict(vide, bloc=_option_imposee(imposee, dict(contexte, **flux)))
    choix = choix_batterie(choix, lead)
    if evaluation is None or choix == 'sans':
        return vide
    bat = catalogue.get('batterie') or {}
    batteries = batteries_compatibles(bat.get('batteries'), bat.get('hybrides'))
    if bat.get('hybrides') and batteries:
        resultat = _dimensionner(catalogue, bat, batteries, evaluation,
                                 production_rasante=production_rasante, **contexte)
    else:
        resultat = {'evaluation': None, 'prix_a_renseigner': [], 'alertes': [], 'hypotheses': [],
                    'motif': 'aucun onduleur hybride basse tension ni batterie basse tension '
                             'à fiche complète au catalogue'}
    sortie = dict(vide, prix_a_renseigner=resultat['prix_a_renseigner'],
                  alertes=list(resultat['alertes']), hypotheses=list(resultat['hypotheses']))
    if bat.get('ecartees'):
        sortie['alertes'].append(_alerte('BATTERIE_FICHE_INCOMPLETE', (
            "Batteries écartées de l'option « avec » (fiche sans capacité utile ni tension "
            'nominale) : %s.' % ', '.join(bat['ecartees']))))
    if choix != 'avec' and resultat['prix_a_renseigner']:
        # Fondateur 27/10/2026 — « les deux » : un article de l'option « avec »
        # sans prix ne refuse pas le devis ; l'offre réseau part seule, les
        # articles sont nommés en alerte INTERNE (jamais au client).
        sortie['prix_a_renseigner'] = []
        sortie['alertes'].append(_alerte('OPTION_BATTERIE_PRIX_A_RENSEIGNER', (
            'Option « avec batterie » non proposée — prix à renseigner : %s.'
            % ', '.join(str(p) for p in resultat['prix_a_renseigner']))))
        return sortie
    if resultat['evaluation'] is None:
        sortie['alertes'].append(_alerte(
            'OPTION_BATTERIE_NON_COMPOSEE', 'Option « avec batterie » non composée : %s.'
            % resultat['motif'], niveau='bloquant' if choix == 'avec' else 'alerte'))
        return sortie
    evalue = resultat['evaluation']
    if _option_dominee(evaluation, evalue):
        sortie['alertes'].append(_alerte_dominee(evaluation, evalue, sortie['alertes'], choix))
        return sortie
    fiche = next((b for b in bat['batteries'] if b['produit'] == evalue['batterie'].get('produit')), None)
    sortie['bloc'] = _bloc(evalue, contexte.get('valoriser'), _ctx_flux(flux, fiche))
    if evalue.get('inclinaison_retenue_deg') is not None:
        # R1 (P2) — clé ADDITIVE : l'inclinaison de la pose qui loge CE champ
        # (30° / rasante 10°), seulement quand le toit plat sans pente la donne.
        sortie['bloc']['inclinaison_retenue_deg'] = evalue['inclinaison_retenue_deg']
    return sortie
