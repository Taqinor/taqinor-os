"""Tests FG40 — facturation récurrente des contrats de maintenance."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance
from apps.ventes.models import Facture

User = get_user_model()
BASE_URL = '/api/django/sav/contrats-maintenance/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _company(slug='fg40-co', nom='FG40 Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _user(co, username='fg40_user'):
    return User.objects.create_user(
        username=username, password='x', role_legacy='responsable', company=co)


def _client(co):
    return Client.objects.create(
        company=co, nom='FG40', prenom='Client',
        email='fg40@example.com', telephone='+212600000055')


def _contrat(co, client, actif=True, prix=Decimal('3000'),
             facturation_active=True, periodicite='annuel',
             derniere_facturation=None):
    return ContratMaintenance.objects.create(
        company=co, client=client,
        periodicite=periodicite,
        date_debut=date(2024, 1, 1),
        actif=actif,
        prix=prix,
        facturation_active=facturation_active,
        derniere_facturation=derniere_facturation,
    )


class TestContratMaintenanceFields(TestCase):
    """Vérifie les nouveaux champs modèle."""

    def setUp(self):
        self.co = _company()
        self.cli = _client(self.co)

    def test_facturation_active_default_false(self):
        c = ContratMaintenance.objects.create(
            company=self.co, client=self.cli,
            periodicite='annuel', date_debut=date(2024, 1, 1))
        self.assertFalse(c.facturation_active)

    def test_derniere_facturation_nullable(self):
        c = ContratMaintenance.objects.create(
            company=self.co, client=self.cli,
            periodicite='annuel', date_debut=date(2024, 1, 1))
        self.assertIsNone(c.derniere_facturation)

    def test_prochaine_facturation_annuel(self):
        c = _contrat(self.co, self.cli, derniere_facturation=date(2024, 1, 1))
        # Annuel : +12 mois → 2025-01-01
        self.assertEqual(c.prochaine_facturation(), date(2025, 1, 1))

    def test_prochaine_facturation_no_derniere_uses_debut(self):
        c = _contrat(self.co, self.cli, derniere_facturation=None)
        # Pas de dernière facturation → base = date_debut = 2024-01-01
        self.assertEqual(c.prochaine_facturation(), date(2025, 1, 1))

    def test_prochaine_facturation_mensuel(self):
        c = _contrat(self.co, self.cli, periodicite='mensuel',
                     derniere_facturation=date(2024, 3, 15))
        self.assertEqual(c.prochaine_facturation(), date(2024, 4, 15))

    def test_facturation_due_inactive_returns_false(self):
        c = _contrat(self.co, self.cli, facturation_active=False)
        self.assertFalse(c.facturation_due())

    def test_facturation_due_actif_false_returns_false(self):
        c = _contrat(self.co, self.cli, actif=False)
        self.assertFalse(c.facturation_due())

    def test_facturation_due_future_returns_false(self):
        # Dernière facturation = aujourd'hui → prochaine = dans 12 mois
        from django.utils import timezone
        today = timezone.localdate()
        c = _contrat(self.co, self.cli, derniere_facturation=today)
        self.assertFalse(c.facturation_due())

    def test_facturation_due_past_returns_true(self):
        # Dernière facturation = 2023-01-01 → prochaine annuelle = 2024-01-01 → due
        c = _contrat(self.co, self.cli, derniere_facturation=date(2023, 1, 1))
        self.assertTrue(c.facturation_due())


class TestFG40Service(TestCase):
    """Tests de apps.ventes.services.creer_facture_contrat."""

    def setUp(self):
        self.co = _company(slug='fg40-svc', nom='FG40 Svc')
        self.user = _user(self.co, username='fg40_svc_user')
        self.cli = _client(self.co)

    def test_creates_facture_emise(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli)
        f = creer_facture_contrat(contrat=c, user=self.user, company=self.co)
        self.assertEqual(f.statut, 'emise')
        self.assertEqual(f.montant_ttc, Decimal('3000'))

    def test_facture_company_scoped(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli)
        f = creer_facture_contrat(contrat=c, user=self.user, company=self.co)
        self.assertEqual(f.company_id, self.co.id)

    def test_derniere_facturation_updated(self):
        from django.utils import timezone
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli)
        today = timezone.localdate()
        creer_facture_contrat(contrat=c, user=self.user, company=self.co)
        c.refresh_from_db()
        self.assertEqual(c.derniere_facturation, today)

    def test_error_when_facturation_inactive(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli, facturation_active=False)
        with self.assertRaises(ValueError):
            creer_facture_contrat(contrat=c, user=self.user, company=self.co)

    def test_error_when_prix_missing(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli, prix=None)
        with self.assertRaises(ValueError):
            creer_facture_contrat(contrat=c, user=self.user, company=self.co)

    def test_error_when_contrat_inactif(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli, actif=False)
        with self.assertRaises(ValueError):
            creer_facture_contrat(contrat=c, user=self.user, company=self.co)

    def test_tva_20_percent(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli, prix=Decimal('6000'))
        f = creer_facture_contrat(contrat=c, user=self.user, company=self.co)
        # TTC = 6000, HT = 5000, TVA = 1000
        self.assertEqual(f.montant_ttc, Decimal('6000'))
        self.assertEqual(f.montant_ht, Decimal('5000.00'))
        self.assertEqual(f.montant_tva, Decimal('1000.00'))

    def test_facture_reference_not_empty(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli)
        f = creer_facture_contrat(contrat=c, user=self.user, company=self.co)
        self.assertTrue(f.reference.startswith('FAC'))

    def test_libelle_contains_contrat_id(self):
        from apps.ventes.services import creer_facture_contrat
        c = _contrat(self.co, self.cli)
        f = creer_facture_contrat(contrat=c, user=self.user, company=self.co)
        self.assertIn(str(c.pk), f.libelle)


class TestFG40Endpoint(TestCase):
    """Tests de l'action POST /sav/contrats-maintenance/{id}/facturer/."""

    def setUp(self):
        self.co = _company(slug='fg40-ep', nom='FG40 EP')
        self.user = _user(self.co, username='fg40_ep_user')
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_facturer_creates_201(self):
        c = _contrat(self.co, self.cli)
        r = self.api.post(f'{BASE_URL}{c.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['ok'])
        self.assertIn('facture_reference', r.data)

    def test_facturer_facture_visible(self):
        c = _contrat(self.co, self.cli)
        r = self.api.post(f'{BASE_URL}{c.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        fac = Facture.objects.filter(
            company=self.co, reference=r.data['facture_reference']).first()
        self.assertIsNotNone(fac)
        self.assertEqual(fac.montant_ttc, Decimal('3000'))

    def test_facturer_inactive_contrat_returns_400(self):
        c = _contrat(self.co, self.cli, facturation_active=False)
        r = self.api.post(f'{BASE_URL}{c.pk}/facturer/')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.data['ok'])

    def test_facturer_no_prix_returns_400(self):
        c = _contrat(self.co, self.cli, prix=None)
        r = self.api.post(f'{BASE_URL}{c.pk}/facturer/')
        self.assertEqual(r.status_code, 400)

    def test_facturer_cross_company_404(self):
        other_co = _company(slug='fg40-other', nom='FG40 Other')
        other_cli = Client.objects.create(
            company=other_co, nom='OtherFG40', email='ofg40@example.com',
            telephone='+212600000054')
        c = _contrat(other_co, other_cli)
        r = self.api.post(f'{BASE_URL}{c.pk}/facturer/')
        self.assertEqual(r.status_code, 404)

    def test_serializer_exposes_facturation_fields(self):
        c = _contrat(self.co, self.cli)
        r = self.api.get(f'{BASE_URL}{c.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('facturation_active', r.data)
        self.assertIn('derniere_facturation', r.data)
        self.assertIn('prochaine_facturation', r.data)
        self.assertIn('facturation_due', r.data)
