# flake8: noqa  (sonde de contre-visite vérifie ATOT, rejouable par scripts/sonde.py — AMET93)
"""ATOT9 : `apps/ventes/views/ligne_facture.py::LigneFactureViewSet.perform_update` ne contrôle que la facture
d'ORIGINE de la ligne (`_check_immuable`) ; `facture` est inscriptible : un PATCH déplace une ligne d'un brouillon vers
une facture émise et change son total. Vraie route, transaction annulée."""
SONDE = {"constat": "C-ATOT-VER-002", "sha": "b72cda218",
         "attendu": "PATCH {facture: <émise>} sur une ligne de brouillon : accepté, la facture émise gagne une ligne"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ATOT VER-002', slug='sonde-atot-ver-002')
    cl = Client.objects.create(company=c, nom='Sonde', prenom='ATOT', email='sonde-atot-ver-002@example.invalid')
    u = U.objects.create_user(username='sonde-atot-ver-002', password='x', role_legacy='responsable', company=c)
    p = Produit.objects.create(company=c, nom='Panneau sonde', sku='SONDE-ATOT-002', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    emise = Facture.objects.create(company=c, reference='FAC-SONDE-ATOT-002', client=cl, statut=Facture.Statut.EMISE,
                                   taux_tva=Decimal('20.00'), created_by=u)
    LigneFacture.objects.create(facture=emise, produit=p, designation='Panneau', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'))
    brouillon = Facture.objects.create(company=c, reference='FAC-SONDE-ATOT-002-BR', client=cl,
                                       statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'), created_by=u)
    li = LigneFacture.objects.create(facture=brouillon, produit=p, designation='Ajout', quantite=Decimal('1'),
                                     prix_unitaire=Decimal('500'))
    ttc_avant = Decimal(str(Facture.objects.get(pk=emise.pk).total_ttc))
    api = APIClient()
    api.force_authenticate(u)
    r = api.patch(f'/api/django/ventes/factures-lignes/{li.id}/', {'facture': emise.id}, format='json',
                  HTTP_HOST='localhost')
    ttc_apres = Decimal(str(Facture.objects.get(pk=emise.pk).total_ttc))
    n = LigneFacture.objects.filter(facture=emise).count()
    print(f'PATCH {r.status_code} lignes_emise={n} ttc {ttc_avant} -> {ttc_apres}')
    return {'repro': r.status_code < 400 and n == 2, 'status': r.status_code, 'ttc_avant': str(ttc_avant),
            'ttc_apres': str(ttc_apres)}
