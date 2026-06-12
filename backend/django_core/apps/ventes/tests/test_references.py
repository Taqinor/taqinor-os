"""
Tests for collision-proof reference numbering (apps.ventes.utils.references).

Reproduces the production crash: count-based numbering generated
DEV-202606-0002 while that reference already existed (the count and the
highest used number drift apart when documents are deleted), raising an
IntegrityError on "Créer le devis".

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_references -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes.models import Devis, BonCommande, Facture
from apps.ventes.utils.references import next_reference, create_with_reference

User = get_user_model()

MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='test-ref-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test Ref Co'},
    )
    return company


def make_user(company):
    return User.objects.create_user(
        username='test_ref_user', password='x', role_legacy='responsable',
        company=company,
    )


def make_client(company):
    return Client.objects.create(
        company=company, nom='Ref', prenom='Test',
        email='ref@example.com', telephone='+212600000001', adresse='Rabat',
    )


def make_devis(company, client, reference):
    return Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
    )


class TestNextReference(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def test_starts_at_one_on_empty_table(self):
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0001')

    def test_uses_highest_existing_number_not_the_count(self):
        # One single row numbered -0002 : the count (1) would regenerate
        # -0002 and crash — the fix must return -0003.
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0002')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0003')

    def test_clears_gaps_and_large_numbers(self):
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0001')
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0010')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0011')

    def test_per_company_isolation(self):
        other = make_company(slug='test-ref-other')
        other_client = Client.objects.create(
            company=other, nom='Autre', email='a@example.com',
            telephone='+212600000002', adresse='Fès',
        )
        make_devis(other, other_client, f'DEV-{MONTH}-0042')
        # The other company's numbers must not leak into ours.
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0001')

    def test_each_model_numbers_independently(self):
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0005')
        self.assertEqual(
            next_reference(BonCommande, 'BC', self.company), f'BC-{MONTH}-0001')
        self.assertEqual(
            next_reference(Facture, 'FAC', self.company), f'FAC-{MONTH}-0001')


class TestCreateWithReferenceRetry(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def test_retries_when_a_concurrent_save_steals_the_number(self):
        from django.db import IntegrityError
        calls = {'n': 0}

        def save_fn(ref):
            calls['n'] += 1
            if calls['n'] == 1:
                # Simulate losing the race: a concurrent request committed the
                # same reference first, so our insert hits the unique
                # constraint. The helper must retry instead of crashing.
                raise IntegrityError(
                    'duplicate key value violates unique constraint '
                    '"ventes_devis_company_id_reference_2a3bcb46_uniq"'
                )
            return make_devis(self.company, self.client_obj, ref)

        devis = create_with_reference(Devis, 'DEV', self.company, save_fn)
        self.assertEqual(calls['n'], 2)
        self.assertTrue(devis.reference.startswith(f'DEV-{MONTH}-'))

    def test_non_reference_integrity_errors_are_not_swallowed(self):
        from django.db import IntegrityError

        def save_fn(ref):
            raise IntegrityError('null value in column "client_id"')

        with self.assertRaises(IntegrityError):
            create_with_reference(Devis, 'DEV', self.company, save_fn)


class TestDevisCreateApiNoCollision(TestCase):
    """End-to-end repro of the founder's crash, through the real endpoint."""

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _create(self):
        return self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')

    def test_create_succeeds_when_next_number_already_taken(self):
        # The exact production scenario: a quote already sits at -0002
        # while only one row exists (count+1 would regenerate -0002).
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0002')
        resp = self._create()
        self.assertEqual(resp.status_code, 201, resp.data)
        ref = Devis.objects.get(pk=resp.data['id']).reference
        self.assertEqual(ref, f'DEV-{MONTH}-0003')

    def test_arbitrary_line_values_persist_exactly(self):
        """A freely-typed price/quantity/discount must be stored and returned
        exactly — no snapping, no drift. 1453 MAD TTC typed on the screen is
        saved as 1210.83 HT and re-displays as exactly 1453 (x1.2, rounded)."""
        from apps.stock.models import Produit
        resp = self._create()
        self.assertEqual(resp.status_code, 201, resp.data)
        produit = Produit.objects.create(
            company=self.company, nom='Module test', sku='MOD-T',
            prix_vente=Decimal('1'), quantite_stock=10,
        )
        line_resp = self.api.post('/api/django/ventes/devis-lignes/', {
            'devis': resp.data['id'],
            'produit': produit.id,
            'designation': 'Module test',
            'quantite': '3.5',
            'prix_unitaire': '1210.83',   # = htFromTtc(1453) côté écran
            'remise': '12.5',
        }, format='json')
        self.assertEqual(line_resp.status_code, 201, line_resp.data)

        detail = self.api.get(f"/api/django/ventes/devis/{resp.data['id']}/")
        ligne = detail.data['lignes'][0]
        self.assertEqual(str(ligne['prix_unitaire']), '1210.83')
        self.assertEqual(str(ligne['quantite']), '3.50')
        self.assertEqual(str(ligne['remise']), '12.50')
        # Re-displayed TTC = exactly the typed 1453, no dirham of drift
        self.assertEqual(round(float(ligne['prix_unitaire']) * 1.2), 1453)

    def test_several_creates_in_a_row_after_a_deletion(self):
        first = self._create()
        second = self._create()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        # Delete the first — the count shrinks, the max stays.
        Devis.objects.get(pk=first.data['id']).delete()
        third = self._create()
        self.assertEqual(third.status_code, 201, third.data)
        ref = Devis.objects.get(pk=third.data['id']).reference
        self.assertEqual(ref, f'DEV-{MONTH}-0003')
