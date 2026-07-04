"""
XFAC11 — Facture consolidée multi-devis/BC d'un même client.

2 devis acceptés du même client donnent 1 facture aux totaux exacts (somme
des deux, TVA par taux correcte), chaque devis marqué facturé, mélange de
clients rejeté, tests.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac11_facture_consolidee -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, FactureSource, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac11-co', nom='XFAC11 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac11@example.com'):
    return Client.objects.create(
        company=company, nom='Consolide', prenom='Client',
        email=email, telephone='+212600000060', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC11FactureConsolideeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac11_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.produit10 = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PV-XFAC11',
            prix_vente=Decimal('1000'), quantite_stock=100,
            tva=Decimal('10.00'),
        )
        self.produit20 = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-XFAC11',
            prix_vente=Decimal('5000'), quantite_stock=10,
            tva=Decimal('20.00'),
        )

    def _accepted_devis(self, ref_suffix, qte_panneau, qte_onduleur):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{ref_suffix}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'),
        )
        LigneDevis.objects.create(
            devis=devis, produit=self.produit10, designation='Panneau PV',
            quantite=Decimal(qte_panneau), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('10.00'),
        )
        LigneDevis.objects.create(
            devis=devis, produit=self.produit20, designation='Onduleur',
            quantite=Decimal(qte_onduleur), prix_unitaire=Decimal('5000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'),
        )
        return devis

    def test_consolidate_two_devis_exact_totals(self):
        d1 = self._accepted_devis('0001', 10, 1)   # 10000 HT10 + 5000 HT20
        d2 = self._accepted_devis('0002', 5, 2)    # 5000 HT10 + 10000 HT20

        r = self.api.post('/api/django/ventes/factures/consolider/', {
            'devis_ids': [d1.id, d2.id],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])

        # Sommes exactes.
        self.assertEqual(facture.total_ht, Decimal('30000'))
        buckets = {b['taux']: b['montant'] for b in facture.tva_par_taux}
        self.assertEqual(buckets[Decimal('10.00')], Decimal('1500.00'))  # 15000*10%
        self.assertEqual(buckets[Decimal('20.00')], Decimal('3000.00'))  # 15000*20%
        self.assertEqual(facture.total_tva, Decimal('4500.00'))
        self.assertEqual(facture.total_ttc, Decimal('34500.00'))

        # Sources tracées.
        sources = FactureSource.objects.filter(facture=facture)
        self.assertEqual(sources.count(), 2)

    def test_devis_marked_facture_after_consolidation(self):
        d1 = self._accepted_devis('0003', 1, 1)
        d2 = self._accepted_devis('0004', 1, 1)
        self.api.post('/api/django/ventes/factures/consolider/', {
            'devis_ids': [d1.id, d2.id],
        }, format='json')
        # Re-consolider les mêmes devis doit être rejeté (déjà facturés).
        d3 = self._accepted_devis('0005', 1, 1)
        r = self.api.post('/api/django/ventes/factures/consolider/', {
            'devis_ids': [d1.id, d3.id],
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_mixed_clients_rejected(self):
        d1 = self._accepted_devis('0006', 1, 1)
        other_client = make_client(self.company, email='other-client@example.com')
        d2 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0007',
            client=other_client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'),
        )
        LigneDevis.objects.create(
            devis=d2, produit=self.produit10, designation='Panneau PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('10.00'),
        )
        r = self.api.post('/api/django/ventes/factures/consolider/', {
            'devis_ids': [d1.id, d2.id],
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_requires_at_least_two_devis(self):
        d1 = self._accepted_devis('0008', 1, 1)
        r = self.api.post('/api/django/ventes/factures/consolider/', {
            'devis_ids': [d1.id],
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_non_accepted_devis_rejected(self):
        d1 = self._accepted_devis('0009', 1, 1)
        d2 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0010',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
        )
        r = self.api.post('/api/django/ventes/factures/consolider/', {
            'devis_ids': [d1.id, d2.id],
        }, format='json')
        self.assertEqual(r.status_code, 400)
