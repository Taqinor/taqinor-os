"""QF6 — Respect the seller's stored avec/sans-batterie choice.

build_quote_data must read etude_params['scenario'] (+ recommended_option)
FIRST and fall back to inference only when absent. « Sans batterie » renders the
réseau option only (no battery, no hybrid inverter); « Avec batterie » renders
the hybrid+battery option only (no réseau inverter); « Les deux » shows both.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qf6_stored_scenario -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company():
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug='test-qf6-co', defaults={'nom': 'Test QF6 Co'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qf6user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Idrissi', prenom='Yassine',
        email='y@example.com', telephone='+212600000003')


# A quote that genuinely carries BOTH options (réseau + hybride + battery).
BOTH_LINES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Batterie Deyness 10 kWh', '1', '14000'),
    ('Installation', '1', '4000'),
]


class TestStoredScenario(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, etude_params, reference):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            etude_params=etude_params)
        for desig, qty, pu in BOTH_LINES:
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'{reference[-6:]}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def test_stored_sans_renders_sans_only(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis({'scenario': 'Sans batterie'}, 'DEV-QF6-SANS')
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertEqual(data['recommended'], 'Sans batterie')
        self.assertEqual(data['nb_options'], 1)
        # one-page list = the sans option (réseau, no battery, no hybrid)
        desigs = [it['designation'].lower() for it in data['all_items']]
        self.assertTrue(any('réseau' in d or 'reseau' in d for d in desigs))
        self.assertFalse(any('hybride' in d for d in desigs))
        self.assertFalse(any('batterie' in d for d in desigs))
        # display total = the sans option total
        self.assertEqual(data['display_total'], data['totaux_sans']['ttc'])

    def test_stored_avec_renders_avec_only(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis({'scenario': 'Avec batterie'}, 'DEV-QF6-AVEC')
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertEqual(data['recommended'], 'Avec batterie')
        self.assertEqual(data['nb_options'], 1)
        desigs = [it['designation'].lower() for it in data['all_items']]
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('batterie' in d for d in desigs))
        self.assertFalse(any('réseau' in d or 'reseau' in d for d in desigs))
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])

    def test_stored_les_deux_shows_both(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            {'scenario': 'Les deux (Sans + Avec)'}, 'DEV-QF6-DEUX')
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Les deux (Sans + Avec)')
        self.assertEqual(data['nb_options'], 2)
        # both option baskets are populated
        self.assertTrue(data['sans_items'])
        self.assertTrue(data['avec_items'])

    def test_recommended_option_stored_honored(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            {'scenario': 'Les deux (Sans + Avec)',
             'recommended_option': 'Sans batterie'}, 'DEV-QF6-RECO')
        data = build_quote_data(devis)
        self.assertEqual(data['recommended'], 'Sans batterie')

    def test_absent_scenario_falls_back_to_inference(self):
        """No stored scenario → the historical inference applies (both options)."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis({}, 'DEV-QF6-NONE')
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Les deux (Sans + Avec)')
        self.assertEqual(data['recommended'], 'Avec batterie')
        self.assertEqual(data['nb_options'], 2)

    def test_stored_avec_but_no_hybrid_falls_back(self):
        """A stored « Avec batterie » that the equipment can't satisfy (réseau
        only) degrades to the available option rather than rendering an empty
        battery option."""
        from apps.ventes.quote_engine import build_quote_data
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QF6-FB',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, etude_params={'scenario': 'Avec batterie'})
        for desig, qty, pu in [
                ('Onduleur réseau 8kW', '1', '14000'),
                ('Panneau mono 550W', '8', '2000')]:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'FB-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        data = build_quote_data(devis)
        # Can't honor « Avec » → degrade to the réseau/sans option.
        self.assertEqual(data['scenario'], 'Sans batterie')
