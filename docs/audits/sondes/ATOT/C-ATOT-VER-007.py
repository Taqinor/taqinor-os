# flake8: noqa  (sonde de contre-visite vérifie ATOT, rejouable par scripts/sonde.py — AMET93)
"""Critique (classe ATOT9) : `apps/ventes/views/facture.py::FactureViewSet.perform_update` ne refuse hors brouillon que
`FACTURE_CHAMPS_ARGENT` ; `client` (sous le seul réglage opt-in `factures_immuables`), `retenue_garantie_mad`, `devise`,
`taux_change` restent modifiables par PATCH sur une facture ÉMISE. Vraie route, transaction annulée."""
SONDE = {"constat": "C-ATOT-VER-007", "sha": "b72cda218",
         "attendu": "PATCH client / retenue_garantie_mad sur une facture émise : accepté, document légal réécrit"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    co = Company.objects.create(nom='Sonde ATOT VER-007', slug='sonde-atot-ver-007')
    u = get_user_model().objects.create_user(username='sonde-atot-ver-007', password='x', company=co, role_legacy='admin')
    a = Client.objects.create(company=co, nom='Client', prenom='A', email='sonde-atot-ver-007a@example.invalid')
    b = Client.objects.create(company=co, nom='Client', prenom='B', email='sonde-atot-ver-007b@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-ATOT-007', prix_vente=Decimal('1000'), quantite_stock=10)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-ATOT-007', client=a, statut=Facture.Statut.EMISE,
                               taux_tva=Decimal('20.00'), created_by=u)
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    api = APIClient()
    api.force_authenticate(u)
    r1 = api.patch(f'/api/django/ventes/factures/{f.pk}/', {'client': b.pk}, format='json', HTTP_HOST='localhost')
    r2 = api.patch(f'/api/django/ventes/factures/{f.pk}/', {'retenue_garantie_mad': '500'}, format='json',
                   HTTP_HOST='localhost')
    f.refresh_from_db()
    print(f'patch_client={r1.status_code} client={f.client_id} (A={a.pk}, B={b.pk}) '
          f'patch_retenue={r2.status_code} retenue={getattr(f, "retenue_garantie_mad", None)}')
    return {'repro': (r1.status_code == 200 and f.client_id == b.pk)
            or (r2.status_code == 200 and str(getattr(f, 'retenue_garantie_mad', '')) in ('500', '500.00')),
            'patch_client': r1.status_code, 'patch_retenue': r2.status_code}
