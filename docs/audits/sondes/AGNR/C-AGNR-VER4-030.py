# flake8: noqa  (sonde d'audit vérifie AGNR lot 4, rejouable par scripts/sonde.py — AMET93)
"""AGNR18 (contre-visite de clôture 04/11) : l'écran (`solar.js::kwcFactureDesLignes` → `kwcPanneauxOption`)
somme quantité × watt de CHAQUE ligne panneau ; le serveur (`quote_engine/lignes_classement.py::panneaux_et_watt_lu`,
lu par `domain/scenario.py::puissance_kwc_du_devis` et `quote_engine/builder.py::build_quote_data`) compte TOUS les
panneaux au watt de la PREMIÈRE ligne lisible. Devis à 10 × 550 W + 10 × 710 W : écran 12,6 kWc (node, même
session), serveur 20 × 550 = 11,0 kWc. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AGNR-VER4-030", "sha": "4cd568403",
         "attendu": "panneaux_et_watt_lu = (20, 550) ; puissance_kwc_du_devis = 11.0 (et non 12.6, le kWc que l'écran affiche et sur lequel il calcule prix/kWc et prix cible)",
         "modeles": ["authentication.Company", "stock.Produit", "ventes.Devis", "ventes.LigneDevis", "crm.Client"]}


def sonde(ctx):
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.quote_engine.lignes_classement import panneaux_et_watt_lu
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    co = Company.objects.create(nom='Sonde AGNR-VER4-030', slug='sonde-agnr-ver4-030')
    cl = Client.objects.create(company=co, nom='Client sonde', email='agnr-ver4-030@example.invalid')
    p550 = Produit.objects.create(company=co, nom='Panneau Jinko 550W', sku='S-AGNR30-550', prix_vente=Decimal('1000'), quantite_stock=0)
    p710 = Produit.objects.create(company=co, nom='Panneau Canadian Solar 710W', sku='S-AGNR30-710', prix_vente=Decimal('1300'), quantite_stock=0)
    ond = Produit.objects.create(company=co, nom='Onduleur réseau Huawei 10kW Triphasé', sku='S-AGNR30-OND', prix_vente=Decimal('15000'), quantite_stock=0)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AGNR-VER4-030', client=cl, statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=d, produit=p550, designation='Panneau Jinko 550W', quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
    LigneDevis.objects.create(devis=d, produit=p710, designation='Panneau Canadian Solar 710W', quantite=Decimal('10'), prix_unitaire=Decimal('1300'))
    LigneDevis.objects.create(devis=d, produit=ond, designation='Onduleur réseau Huawei 10kW Triphasé', quantite=Decimal('1'), prix_unitaire=Decimal('15000'))
    lignes = list(d.lignes.select_related('produit').all())
    nb, watt = panneaux_et_watt_lu(lignes)
    kwc_srv = puissance_kwc_du_devis(d)
    somme_par_ligne = sum(float(l.quantite) * w for l, w in zip(lignes[:2], (550, 710))) / 1000
    obs = {'panneaux_et_watt_lu': [nb, watt], 'puissance_kwc_du_devis': float(kwc_srv) if kwc_srv is not None else None,
           'kwc_somme_par_ligne_ecran': somme_par_ligne}
    try:
        from apps.ventes.quote_engine.builder import build_quote_data
        q = build_quote_data(d)
        obs['build_quote_data.puissance_kwc'] = q.get('puissance_kwc')
        obs['build_quote_data.nb_panneaux'] = q.get('nb_panneaux')
        obs['build_quote_data.watt'] = q.get('watt')
    except Exception as exc:  # le rendu complet peut exiger plus de contexte : noté, pas un verdict
        obs['build_quote_data_erreur'] = repr(exc)[:300]
    print(obs)
    repro = (nb == 20 and watt == 550 and kwc_srv is not None and abs(float(kwc_srv) - 11.0) < 0.01
             and abs(somme_par_ligne - 12.6) < 0.01)
    return {'repro': repro, **obs}
