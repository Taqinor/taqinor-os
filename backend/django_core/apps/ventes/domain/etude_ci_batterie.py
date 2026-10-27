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


def _bloc(evaluation, valoriser=None):
    """La forme servie ``etude['option_avec']`` (jamais ``prix_achat``) : le
    bilan SANS sa ventilation horaire (le PDF et l'écran lisent les totaux),
    l'``economie_ci`` complète quand le valoriseur la sert (document à option
    « avec » seule), le coût de vente HT et le retour simple quand la
    composition est connue (étude ; le rafraîchisseur lit les totaux des
    lignes)."""
    from .etude_ci import _forme_composition
    from decimal import ROUND_HALF_UP, Decimal

    from core.money import quantize_mad
    economie, cout = evaluation.get('economie'), evaluation.get('cout')
    complet = getattr(valoriser, 'complet', None)
    retour = None
    if cout and economie:
        retour = float((Decimal(str(cout)) / Decimal(str(economie))).quantize(
            Decimal('0.1'), rounding=ROUND_HALF_UP))
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
        'economie_ci': complet(evaluation['bilan']) if complet else None,
        'economie_annuelle_mad': None if economie is None else round(economie, 2),
        'cout_vente_ht': None if cout is None else float(quantize_mad(str(cout))),
        'retour_simple_ans': retour,
    }


def _alerte(code, message, niveau='alerte'):
    return {'code': code, 'champ': 'option_avec', 'message': message,
            'niveau': niveau, 'interne': True}


def _dimensionner(catalogue, bat, batteries, evaluation, *, phase, ps_kva, composer,
                  borne_toit, **noyau):
    from apps.ventes.etude_horaire import simuler_batterie_jour
    from apps.ventes.moteur_ci.batterie import (
        MAX_HYBRIDES_PARALLELE, dimensionner_option_avec,
    )
    from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
    return dimensionner_option_avec(
        simuler=simuler_batterie_jour,
        kwc_depart=evaluation['kwc'], pmax_wc=(catalogue.get('module') or {}).get('pmax_wc'),
        combiner=lambda kwc: combiner_onduleurs(
            kwc, bat['hybrides'], phase=phase, module=catalogue.get('module_spec'),
            ac_max_kw=ps_kva, max_appareils=MAX_HYBRIDES_PARALLELE),
        composer=lambda kwc, onduleurs: composer(kwc, onduleurs, bat.get('elements')),
        batteries=batteries, hybrides=bat['hybrides'], kwc_max=(borne_toit or {}).get('kwc'),
        ps_kva=ps_kva, **noyau)


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


def option_imposee_des_lignes(lignes, catalogue, kwc, nb_panneaux=None):
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
            'onduleurs': {'combinaison': [dict(hybrides[p], quantite=q) for p, q in sorted(q_h.items())]},
            'hybrides': list(hybrides.values()),
            'empreinte': [kwc, sorted(q_h.items()), sorted(q_b.items())]}


def _option_imposee(imposee, contexte):
    """Le bilan et l'économie de l'option « avec » des lignes (aucun
    redimensionnement, aucune composition : le coût est celui des lignes)."""
    from apps.ventes.etude_horaire import simuler_batterie_jour
    from apps.ventes.moteur_ci.batterie import evaluer_option_avec
    evaluation = evaluer_option_avec(
        imposee['kwc'], imposee['onduleurs'], None, imposee['banque'],
        charge=contexte['charge'], production=contexte['production'],
        tension=contexte['tension'], revente_choisie=contexte['revente_choisie'],
        valoriser=contexte['valoriser'], simuler=simuler_batterie_jour,
        hybrides=imposee['hybrides'], taux_tva_pct=contexte.get('taux_tva_pct'))
    bloc = _bloc(evaluation, contexte['valoriser'])
    bloc['nb_panneaux'] = imposee.get('nb_panneaux')
    return bloc


def option_avec_de_l_etude(catalogue, evaluation, *, choix, lead, imposee=None, **contexte):
    """``{bloc, prix_a_renseigner, alertes, hypotheses}`` de l'option « avec
    batterie » d'une étude C&I dont l'option « sans » est ``evaluation``.
    ``contexte`` : ``charge, production, tension, revente_choisie, valoriser,
    taux_tva_pct`` (noyau) + ``phase, ps_kva, composer, borne_toit``.
    ``imposee`` (rafraîchisseur CIQ119) : l'option des LIGNES
    (:func:`option_imposee_des_lignes`), évaluée telle quelle.
    Choix « sans » ⇒ rien ; choix « avec » non composable ⇒ alerte BLOQUANTE
    (refus nommé) ; « les deux » non composable ⇒ alerte interne, l'option
    « sans » reste seule."""
    vide = {'bloc': None, 'prix_a_renseigner': [], 'alertes': [], 'hypotheses': []}
    if imposee is not None:
        return dict(vide, bloc=_option_imposee(imposee, contexte))
    choix = choix_batterie(choix, lead)
    if evaluation is None or choix == 'sans':
        return vide
    bat = catalogue.get('batterie') or {}
    batteries = batteries_compatibles(bat.get('batteries'), bat.get('hybrides'))
    if bat.get('hybrides') and batteries:
        resultat = _dimensionner(catalogue, bat, batteries, evaluation, **contexte)
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
    sortie['bloc'] = _bloc(resultat['evaluation'], contexte.get('valoriser'))
    return sortie
