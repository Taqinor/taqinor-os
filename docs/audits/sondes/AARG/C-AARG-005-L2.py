# flake8: noqa  (seconde lentille PA4 « Argent » sur K05, rejouable par scripts/sonde.py — AMET93)
"""K05, reproduction INDÉPENDANTE : facture À LIGNES PRODUIT (2 × 500 HT, 20 % → 1 200 TTC / TVA 200), avoir par le
RETOUR CLIENT d'une unité (`retour-client` → 600 TTC / TVA 100), puis paiement 400 + RAS-TVA 100 % par la VRAIE
ROUTE `paiements/factures/<id>/paiement-avec-retenue/`, rôle canonique Directeur (porteur d'`encaisser`).
Attendu fiscal : la TVA restant due par le client après l'avoir = 100 → RAS 100, 100 encore dus. D-ASTK-171 (« toute
la TVA de la facture », acompte compris) ne dit rien des avoirs. Transaction annulée."""
SONDE = {"constat": "C-AARG-005-L2", "sha": "56d5b623a",
         "attendu": "RAS-TVA 100 % après retour de 600 TTC (TVA 100) = 100 ; facture non soldée (100 dus)",
         "modeles": ["ventes.Facture", "ventes.LigneFacture", "ventes.Avoir", "ventes.Paiement", "ventes.RetenueSubie"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Avoir, RetenueSubie
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 105', slug='sonde-aarg-105')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-aarg105-dir', password='x', company=co, role=r_dir)
    cl = Client.objects.create(company=co, nom='Public', prenom='K05bis', email='sonde-aarg-105@example.invalid')
    p = Produit.objects.create(company=co, nom='Panneau K05', sku='SONDE-AARG-105', prix_vente=Decimal('500'),
                               quantite_stock=10)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG-105', client=cl, statut=Facture.Statut.EMISE,
                               taux_tva=Decimal('20.00'), date_emission=date.today(), created_by=u)
    LigneFacture.objects.create(facture=f, produit=p, designation='Panneau', quantite=Decimal('2'),
                                prix_unitaire=Decimal('500'), taux_tva=Decimal('20.00'))
    api = APIClient()
    api.force_authenticate(u)
    rr = api.post(f'/api/django/ventes/factures/{f.id}/retour-client/',
                  {'motif': 'Panneau rendu', 'restocker': False, 'lignes': [{'produit': p.id, 'quantite': '1'}]},
                  format='json', **H)
    av = Avoir.objects.filter(facture=f, statut='emise').first()
    f = Facture.objects.get(pk=f.pk)
    du_apres_avoir = f.montant_du
    rp = api.post(f'/api/django/ventes/paiements/factures/{f.id}/paiement-avec-retenue/',
                  {'montant': '400.00', 'date_paiement': date.today().isoformat(), 'mode': 'virement',
                   'type_retenue': 'ras_tva', 'taux': '100'}, format='json', **H)
    f = Facture.objects.get(pk=f.pk)
    ret = RetenueSubie.objects.filter(facture=f).first()
    obs = {'http_retour': rr.status_code, 'avoir_ttc': str(av.total_ttc) if av else None,
           'avoir_tva': str(av.total_tva) if av else None, 'facture_total_tva': str(f.total_tva),
           'du_apres_avoir': str(du_apres_avoir), 'http_ras': rp.status_code,
           'ras_detail': (rp.data if rp.status_code >= 400 else None),
           'ras_base': str(ret.base) if ret else None, 'ras_montant': str(ret.montant) if ret else None,
           'statut_final': f.statut, 'montant_du_final': str(f.montant_du)}
    print(obs)
    obs['repro'] = (rr.status_code in (200, 201) and rp.status_code in (200, 201) and ret is not None
                    and ret.montant > Decimal('100.01'))
    return obs
