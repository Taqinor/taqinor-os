"""QX21be — création/édition atomique d'un devis (create AND edit).

  * POST /devis/atomic/ crée devis + lignes en un commit (company forcée) ;
  * POST /devis/<id>/replace-lines/ remplace les lignes atomiquement ;
  * un produit d'une autre société est refusé (rollback, aucune ligne créée).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class Qx21AtomicDevisTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx21-co', defaults={'nom': 'QX21 Co'})
        self.user = User.objects.create_user(
            username='qx21_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX21',
            telephone='+212600000056')
        self.p1 = Produit.objects.create(
            company=self.company, nom='Panneau', sku='QX21-PV',
            prix_vente=Decimal('1000'), quantite_stock=100)
        self.p2 = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='QX21-OND',
            prix_vente=Decimal('2000'), quantite_stock=100)

    def test_atomic_create_devis_with_lines(self):
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id,
            'statut': 'brouillon', 'taux_tva': '20',
            'lignes': [
                {'produit': self.p1.id, 'quantite': '10',
                 'prix_unitaire': '1000'},
                {'produit': self.p2.id, 'quantite': '1',
                 'prix_unitaire': '2000'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        devis = Devis.objects.get(id=resp.data['id'])
        self.assertEqual(devis.lignes.count(), 2)
        self.assertEqual(devis.company_id, self.company.id)

    def test_atomic_create_rejects_no_lines(self):
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20', 'lignes': [],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Devis.objects.count(), 0)

    def test_atomic_create_rollback_on_bad_product(self):
        other = Company.objects.create(slug='qx21-other', nom='Other')
        foreign = Produit.objects.create(
            company=other, nom='X', sku='QX21-FOR',
            prix_vente=Decimal('1'), quantite_stock=1)
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20',
            'lignes': [{'produit': foreign.id, 'quantite': '1',
                        'prix_unitaire': '1'}],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        # Rollback total : aucun devis créé.
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_replace_lines_atomic(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX2101',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.user)
        from apps.ventes.models import LigneDevis
        LigneDevis.objects.create(
            devis=devis, produit=self.p1, designation='Old',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/', {
                'lignes': [
                    {'produit': self.p2.id, 'quantite': '3',
                     'prix_unitaire': '2000'},
                ],
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        devis.refresh_from_db()
        self.assertEqual(devis.lignes.count(), 1)
        self.assertEqual(devis.lignes.first().produit_id, self.p2.id)

    def test_replace_lines_rollback_preserves_old(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX2102',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.user)
        from apps.ventes.models import LigneDevis
        LigneDevis.objects.create(
            devis=devis, produit=self.p1, designation='Keep',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/', {
                'lignes': [{'produit': 999999, 'quantite': '1',
                            'prix_unitaire': '1'}],
            }, format='json')
        self.assertEqual(resp.status_code, 400)
        devis.refresh_from_db()
        # Rollback : la ligne d'origine survit.
        self.assertEqual(devis.lignes.count(), 1)
        self.assertEqual(devis.lignes.first().designation, 'Keep')
