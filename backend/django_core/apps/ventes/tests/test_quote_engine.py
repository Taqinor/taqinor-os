"""
Tests for the premium quote engine (apps.ventes.quote_engine).

Covers the OS-quote -> data-dict mapping (power derivation, split-by-battery,
on-the-fly ROI) and a full premium PDF render with MinIO mocked.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company():
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug='test-qe-co', defaults={'nom': 'Test QE Co'},
    )
    return company


def make_user(company):
    return User.objects.create_user(
        username='test_qe_user', password='x', role_legacy='responsable',
        company=company,
    )


def make_client(company):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Karim',
        email='k@example.com', telephone='+212600000000',
        adresse='Hay Riad, Rabat',
    )


def make_produit(company, nom, sku, prix):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(prix), prix_achat=Decimal('1'),
        quantite_stock=100,
    )


def make_devis(company, user, client, lignes, remise_globale='0'):
    devis = Devis.objects.create(
        company=company, reference='DEV-QE-0001', client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal(remise_globale), created_by=user,
    )
    for desig, qty, pu in lignes:
        LigneDevis.objects.create(
            devis=devis, produit=make_produit(company, desig, desig[:20], pu),
            designation=desig, quantite=Decimal(qty),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
        )
    return devis


class TestBuildQuoteData(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_power_derived_from_panels(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ])
        data = build_quote_data(devis)
        # 10 panels x 450W = 4.5 kWc
        self.assertEqual(data['nb_panneaux'], 10)
        self.assertEqual(data['watt_par_panneau'], 450)
        self.assertEqual(data['puissance_kwc'], 4.5)
        # ROI fields present and sane
        self.assertGreater(data['prod_kwh'], 0)
        self.assertGreater(data['eco_a_ann'], 0)
        self.assertIn('eco_s_monthly', data)
        self.assertEqual(len(data['eco_s_monthly']), 12)

    def test_split_by_battery_autoadds_when_absent(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '8', '2000'),
            ('Onduleur reseau', '1', '14000'),
        ])
        data = build_quote_data(devis)
        # No battery in quote -> Option 2 (avec) gets one added, Option 1 doesn't.
        self.assertEqual(len(data['sans_items']), 2)
        self.assertEqual(len(data['avec_items']), 3)
        self.assertTrue(
            any('batterie' in it['designation'].lower() for it in data['avec_items'])
        )
        # Avec total strictly greater than sans (battery added).
        self.assertGreater(data['total_avec'], data['total_sans'])

    def test_existing_battery_not_duplicated(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '6', '1500'),
            ('Batterie 5 kWh', '1', '16000'),
        ])
        data = build_quote_data(devis)
        # Battery already present: sans excludes it, avec keeps the single one.
        self.assertEqual(len(data['sans_items']), 1)
        self.assertEqual(len(data['avec_items']), 2)
        batteries = [it for it in data['avec_items']
                     if 'batterie' in it['designation'].lower()]
        self.assertEqual(len(batteries), 1)

    def test_ttc_conversion_and_global_discount(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1000'),
        ], remise_globale='10')
        data = build_quote_data(devis)
        # 10 x 1000 HT x1.20 TTC = 12000 before; -10% global = 10800.
        self.assertEqual(data['total_sans_before'], 12000.0)
        self.assertEqual(data['discount_pct'], 10.0)
        self.assertEqual(data['total_sans'], 10800)


class TestPremiumPdfRender(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    @patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket')
    @patch('apps.ventes.utils.pdf._upload_pdf')
    def test_generate_premium_pdf_produces_pdf_bytes(self, mock_upload, mock_bucket):
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '12', '1500'),
            ('Onduleur hybride', '1', '12000'),
            ('Structures acier', '12', '450'),
        ])
        key = generate_premium_devis_pdf(devis.id)

        # Stored under company-scoped key, persisted on the model.
        self.assertEqual(key, f'devis/{self.company.id}/{devis.reference}.pdf')
        devis.refresh_from_db()
        self.assertEqual(devis.fichier_pdf, key)

        # Real PDF bytes were uploaded.
        mock_upload.assert_called_once()
        pdf_bytes = mock_upload.call_args[0][0]
        self.assertTrue(pdf_bytes[:4] == b'%PDF')
        self.assertGreater(len(pdf_bytes), 5000)
