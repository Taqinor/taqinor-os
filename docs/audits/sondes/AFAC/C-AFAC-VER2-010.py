# flake8: noqa  (contre-visite « vérifie AFAC » 2, rejouable par scripts/sonde.py — AMET93)
"""AFAC27 par le VRAI panier de facturation (`facturation_ops.copier_devis_sur_facture`, geste partagé par
`facturer-complet` et `bon_commande.creer_facture`) : le test AFAC27 crée la facture à la main (remise 15 %
SANS palier, ou palier SANS remise). Ici : devis remisé 15 % + palier ARRONDI-100 posé par le panier,
2 × 10 037 HT, TVA 20 %. Deux retours d'une unité par l'API `retour-client` (admin). Attendu sain :
deux 201, Σ avoirs = TTC facturé au centime, avoir 1 ≈ moitié du TTC facturé (prorata), remise_globale 15
sur chaque avoir. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AFAC-VER2-010", "sha": "1dfa7986c",
         "attendu": "retour 1 → 201 ; retour 2 → 201 ; Σ avoirs == facture.total_ttc ; |avoir1 − TTC/2| ≤ 0.01 ; remise_globale avoir = 15",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.Avoir", "ventes.Devis"]}


def sonde(ctx):
    import inspect
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, Facture, Avoir
    from apps.ventes.domain import facturation_ops as fo
    code_ok = hasattr(fo, 'creer_avoir_facture') and 'TVA-MELANGEE' in inspect.getsource(fo._figer_avoir_retour)
    co = Company.objects.create(nom='Sonde AFAC-VER2-010', slug='sonde-afac-ver2-010')
    u = get_user_model().objects.create_user(username='sonde-afac-ver2-010', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client VER2', email='ver2-010@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-AFAC-V2-010', prix_vente=Decimal('10037'), quantite_stock=0)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AFACV2-010', client=cl, statut=Devis.Statut.ACCEPTE,
                             taux_tva=Decimal('20'), remise_globale=Decimal('15'))
    LigneDevis.objects.create(devis=d, produit=p, designation='Onduleur', quantite=Decimal('2'),
                              prix_unitaire=Decimal('10037'), taux_tva=Decimal('20'))
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AFACV2-010', client=cl, devis=d,
                               statut='emise', taux_tva=Decimal('20'))
    fo.copier_devis_sur_facture(f, d)
    f = Facture.objects.get(pk=f.pk)
    api = APIClient()
    api.force_authenticate(u)
    url = f'/api/django/ventes/factures/{f.pk}/retour-client/'
    corps = {'motif': 'sonde', 'restocker': False, 'lignes': [{'produit': p.pk, 'quantite': 1}]}
    r1 = api.post(url, corps, format='json', HTTP_HOST='localhost')
    r2 = api.post(url, corps, format='json', HTTP_HOST='localhost')
    avoirs = list(Avoir.objects.filter(facture=f).order_by('id'))
    f = Facture.objects.get(pk=f.pk)
    ttc = Decimal(str(f.total_ttc))
    a = [Decimal(str(x.total_ttc)) for x in avoirs]
    obs = {'code_afac27_present': code_ok, 'arrondi_pas': f.arrondi_pas, 'remise_globale': str(f.remise_globale),
           'facture_ttc': str(ttc), 'r1': (r1.status_code, r1.data if r1.status_code >= 400 else None),
           'r2': (r2.status_code, r2.data if r2.status_code >= 400 else None),
           'avoirs_ttc': [str(x) for x in a], 'avoirs_remise': [str(x.remise_globale) for x in avoirs],
           'somme_avoirs': str(sum(a, Decimal('0'))), 'montant_du': str(f.montant_du)}
    print(obs)
    sain = (r1.status_code == 201 and r2.status_code == 201 and len(a) == 2 and sum(a, Decimal('0')) == ttc
            and abs(a[0] - ttc / 2) <= Decimal('0.01') and all(x.remise_globale == Decimal('15') for x in avoirs))
    return {'repro': sain, **obs}
