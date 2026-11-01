# flake8: noqa  (sonde de contre-visite vérifie AANA, rejouable par scripts/sonde.py — AMET93)
"""AANA20 : `reporting/views.py::_ht_encaisse` compte comme encaissé le total HT d'une facture passée « payée » par un
avoir total (mode correction, `montant_du` à 0) alors qu'aucun paiement n'a été reçu. Vraies routes, transaction annulée."""
SONDE = {"constat": "C-AANA-VER-002", "sha": "32375fe65",
         "attendu": "facture 1000 HT émise, avoir total sans paiement : CA encaissé HT du tableau de bord > 0 (attendu 0)"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    co = Company.objects.create(nom='Sonde AANA VER-002', slug='sonde-aana-ver-002')
    u = get_user_model().objects.create_user(username='sonde-aana-ver-002', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Cli', prenom='V002', email='sonde-aana-ver-002@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AANA-002', prix_vente=Decimal('1000'), quantite_stock=0)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AANA-002', client=cl, statut='emise',
                               taux_tva=Decimal('20.00'))
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), remise=Decimal('0'), taux_tva=Decimal('20.00'))
    api = APIClient()
    api.force_authenticate(u)
    r1 = api.post(f'/api/django/ventes/factures/{f.pk}/creer-avoir/', {'motif': 'Annulation commerciale'},
                  format='json', HTTP_HOST='localhost')
    f.refresh_from_db()
    r2 = api.get('/api/django/reporting/dashboard/', HTTP_HOST='localhost')
    kpis = r2.data.get('kpis', {}) if r2.status_code == 200 and isinstance(r2.data, dict) else {}
    print(f'avoir={r1.status_code} statut={f.statut} dashboard={r2.status_code} '
          f'ca_paye={kpis.get("ca_paye")} ca_attente={kpis.get("ca_attente")} (attendu ca_paye 0)')
    return {'repro': r1.status_code in (200, 201) and float(kpis.get('ca_paye') or 0) > 0,
            'avoir': r1.status_code, 'statut': f.statut, 'ca_paye': kpis.get('ca_paye'),
            'ca_attente': kpis.get('ca_attente')}
