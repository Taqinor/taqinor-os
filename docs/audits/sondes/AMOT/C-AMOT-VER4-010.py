# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT57 (union des familles d'onduleur) × AMOT29/AMOT102 (payback publié des cartes et paliers).

Le PDF (`quote_engine/lignes_classement.py::_cout_onduleur`, prédicat `is_inverter` = union des familles depuis
AMOT57) provisionne le remplacement d'un onduleur AUTONOME (« Onduleur hors-réseau Deye 6kW », rôle
`onduleur_offgrid`, composé pour un site isolé par `domain/composition_residentielle.py`). Les deux constructeurs de
provision des surfaces /proposition — `offres_tailles.py::_cout_onduleur_ttc` (cartes Éco/Max) et
`domain/dimensionnement_devis.py::_payback_publie_palier` (échelle de paliers) — filtrent sur les seuls rôles
`onduleur_reseau` / `onduleur_hybride` : la provision de l'onduleur autonome disparaît, le payback publié est plus
court que la définition du document. Fonctions pures du code de `main`, aucune écriture. Jamais contre la prod."""
SONDE = {"constat": "C-AMOT-VER4-010", "sha": "c38868a62",
         "attendu": "même ligne onduleur (15 000 HT) : PDF provision 18 000 ; carte Éco/Max provision None si rôle onduleur_offgrid (18 000 si onduleur_hybride) ; palier d'échelle 90 000 / 6 500 : payback plus court en offgrid qu'en hybride (provision oubliée)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis"]}


def sonde(ctx):
    from types import SimpleNamespace as NS
    from apps.ventes import offres_tailles as ot
    from apps.ventes.domain.dimensionnement_devis import _payback_publie_palier
    from apps.ventes.domain.regles_calcul import REGLES_COURANTES
    from apps.ventes.quote_engine.lignes_classement import _cout_onduleur
    from apps.ventes.quote_engine.pricing import compute_cashflow_payback
    from apps.ventes.solar_classification import is_inverter, is_offgrid_inverter
    des = 'Onduleur hors-réseau Deye 6kW'
    obs = {'is_inverter': is_inverter(des), 'is_offgrid_inverter': is_offgrid_inverter(des)}
    # PDF : provision = prix TTC de la ligne (18 000 = 15 000 HT × 1,2)
    obs['pdf_provision'] = _cout_onduleur([{'designation': des, 'quantite': 1, 'prix_unit_ttc': 18000}])
    ligne = NS(quantite=1, prix_unitaire=15000, produit=None, designation=des)
    obs['carte_provision_offgrid'] = ot._cout_onduleur_ttc([ligne], ['onduleur_offgrid'], 1.0, 20, None)
    obs['carte_provision_hybride'] = ot._cout_onduleur_ttc([ligne], ['onduleur_hybride'], 1.0, 20, None)
    obs['carte_payback_offgrid'] = ot._payback_publie(90000.0, 6500.0, stockage=True, part_batterie=0.0,
                                                      cout_onduleur_ttc=obs['carte_provision_offgrid'])
    obs['carte_payback_hybride'] = ot._payback_publie(90000.0, 6500.0, stockage=True, part_batterie=0.0,
                                                      cout_onduleur_ttc=obs['carte_provision_hybride'])
    devis = NS(regles_calcul=REGLES_COURANTES, company=None)
    lp = lambda role: [{'role': role, 'quantite': 1, 'prix_unitaire_ht': 15000.0, 'designation': des}]
    obs['palier_payback_offgrid'] = _payback_publie_palier(90000.0, 6500.0, lp('onduleur_offgrid'), 1.0,
                                                           devis=devis, taux_tva=20)
    obs['palier_payback_hybride'] = _payback_publie_palier(90000.0, 6500.0, lp('onduleur_hybride'), 1.0,
                                                           devis=devis, taux_tva=20)
    obs['pdf_roi_a_definition'] = round(compute_cashflow_payback(
        90000.0, 6500.0, battery=True, battery_share=0.0, inverter_replace_cost=18000.0)['payback_years'], 2)
    print(obs)
    repro = (obs['is_inverter'] and obs['pdf_provision'] and obs['carte_provision_offgrid'] is None
             and obs['carte_provision_hybride']
             and obs['palier_payback_offgrid'] is not None and obs['palier_payback_hybride'] is not None
             and obs['palier_payback_offgrid'] < obs['palier_payback_hybride'])
    return {'repro': bool(repro), **obs}
