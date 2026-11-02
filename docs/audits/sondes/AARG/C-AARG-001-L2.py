# flake8: noqa  (seconde lentille PA4 « Argent » sur K01, rejouable par scripts/sonde.py — AMET93)
"""K01, reproduction INDÉPENDANTE : chemin écran le plus courant — facture À LIGNES PRODUIT (2 × 1 000 HT, 20 %),
soldée par la vraie route `enregistrer-paiement`, puis RETOUR CLIENT d'une unité (`retour-client`, qui accepte
explicitement une facture « payée »), le tout par un rôle canonique Directeur (porteur d'`encaisser`, pas l'admin
hérité). On mesure : avoir créé ? reste dû négatif ? avance / trop-perçu ? relevé client par la vraie route
`clients/<id>/releve/` ? Transaction annulée."""
SONDE = {"constat": "C-AARG-001-L2", "sha": "56d5b623a",
         "attendu": "facture 2 400 TTC payée 2 400, retour 1 unité (1 200 TTC) → refusé, OU 1 200 dus au client visibles "
                    "(avance / trop-perçu / solde négatif au relevé)",
         "modeles": ["ventes.Facture", "ventes.LigneFacture", "ventes.Avoir", "ventes.Paiement"]}


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
    from apps.ventes.models import Facture, LigneFacture, Paiement, Avoir
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 101', slug='sonde-aarg-101')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-aarg101-dir', password='x', company=co, role=r_dir)
    cl = Client.objects.create(company=co, nom='Retour', prenom='K01bis', email='sonde-aarg-101@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur K01', sku='SONDE-AARG-101', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG-101', client=cl, statut=Facture.Statut.EMISE,
                               taux_tva=Decimal('20.00'), date_emission=date.today(), created_by=u)
    LigneFacture.objects.create(facture=f, produit=p, designation='Onduleur', quantite=Decimal('2'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    f = Facture.objects.get(pk=f.pk)
    ttc = f.total_ttc
    api = APIClient()
    api.force_authenticate(u)
    rp = api.post(f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
                  {'montant': str(ttc), 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                  format='json', **H)
    f = Facture.objects.get(pk=f.pk)
    statut_avant = f.statut
    rr = api.post(f'/api/django/ventes/factures/{f.id}/retour-client/',
                  {'motif': 'Client rend un onduleur', 'restocker': False,
                   'lignes': [{'produit': p.id, 'quantite': '1'}]}, format='json', **H)
    f = Facture.objects.get(pk=f.pk)
    avoirs = list(Avoir.objects.filter(facture=f).values_list('reference', 'montant_ttc', 'statut'))
    avoir_ttc = sum((a.total_ttc for a in Avoir.objects.filter(facture=f, statut='emise')), Decimal('0'))
    avances = [str(x.montant) for x in Paiement.objects.filter(company=co, facture__isnull=True)]
    rel = api.get(f'/api/django/ventes/clients/{cl.id}/releve/', **H)
    rel_d = rel.data if rel.status_code == 200 else {'http': rel.status_code}
    totaux = rel_d.get('totaux') if isinstance(rel_d, dict) else None
    obs = {'ttc': str(ttc), 'http_paiement': rp.status_code, 'statut_avant': statut_avant,
           'http_retour': rr.status_code, 'retour_detail': (rr.data if rr.status_code >= 400 else None),
           'avoirs': [(a[0], str(a[1]), a[2]) for a in avoirs], 'avoir_ttc_actif': str(avoir_ttc),
           'statut_apres': f.statut, 'montant_paye': str(f.montant_paye), 'avoirs_total': str(f.avoirs_total),
           'montant_du': str(f.montant_du), 'avances_client': avances, 'http_releve': rel.status_code,
           'releve_totaux': totaux}
    print(obs)
    du_rel = None
    try:
        du_rel = Decimal(str((totaux or {}).get('du')))
    except Exception:
        pass
    credit_visible = bool(avances) or Decimal(str(f.montant_du)) < 0 or (du_rel is not None and du_rel < 0)
    obs['repro'] = (rp.status_code in (200, 201) and rr.status_code in (200, 201) and avoir_ttc > 0
                    and not credit_visible)
    return obs
