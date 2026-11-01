# flake8: noqa  (sonde de contre-visite vérifie AMOT, rejouable par scripts/sonde.py — AMET93)
"""AMOT102 / AMOT107 sur un VRAI devis persisté (niveau de règles par défaut) : le palier de l'échelle
(`_payback_publie_palier`, devis réel) et la carte « avec » de repli (`_carte_du_devis`, lignes réelles via
`lignes_vendues`) publient-ils la définition de `roi_a` (stockage, part stockée 0, provision onduleur TTC) ?
Repro = l'un des deux diverge de payback_publiable(90 000, 6 500, part 0, onduleur 15 000)."""
SONDE = {"constat": "C-AMOT-VER-010", "sha": "56d5b623a",
         "attendu": "palier et repli « avec » = définition roi_a (16,8 sur le cas sonde), pas 18,8"}


def sonde(ctx):
    from decimal import Decimal
    from types import SimpleNamespace
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes import offres_tailles as ot
    from apps.ventes.domain.dimensionnement_devis import _payback_publie_palier
    from apps.ventes.quote_engine.pricing import payback_publiable
    co = Company.objects.create(nom='Sonde AMOT VER-010', slug='sonde-amot-ver-010')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER010', email='sonde-amot-ver-010@example.invalid')
    dv = Devis.objects.create(company=co, client=cl, reference='DEV-SONDE-AMOT-010', statut='brouillon',
                              taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=dv, designation='Onduleur hybride Deye 5kW', quantite=Decimal('1'),
                              prix_unitaire=Decimal('12500'))
    LigneDevis.objects.create(devis=dv, designation='Batterie Dyness 5kWh', quantite=Decimal('2'),
                              prix_unitaire=Decimal('15000'))
    attendu = payback_publiable(90000, 6500, stockage=True, part_batterie=0.0,
                                cout_onduleur_ttc=15000)['payback_years']
    lignes = [{'role': 'onduleur_hybride', 'quantite': 1, 'prix_unitaire_ht': 12500.0,
               'designation': 'Onduleur hybride Deye 5kW'}]
    palier = _payback_publie_palier(90000.0, 6500.0, lignes, 1.0, devis=dv, taux_tva=dv.taux_tva)
    from apps.ventes.tests.test_offres_tailles import _contexte_factice
    data = {'nb_panneaux_avec': 22, 'puissance_kwc_avec': 12.1, 'totaux_avec': {'ttc': 90000.0},
            'eco_a_ann': 6500.0}
    carte = ot._carte_du_devis(_contexte_factice(dv), data, 'avec') or {}
    repli = carte.get('payback_annees')
    print(f'regles={dv.regles_calcul} attendu_roi_a={attendu} palier={palier} repli_avec={repli}')
    ecart = lambda v: v is None or abs(float(v) - float(attendu)) > 0.05
    return {'repro': ecart(palier) or ecart(repli), 'attendu': attendu, 'palier': palier, 'repli': repli}
