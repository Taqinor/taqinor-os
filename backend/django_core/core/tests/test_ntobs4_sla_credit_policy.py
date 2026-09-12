"""NTOBS4 — crédits SLA calculés automatiquement selon un barème contractuel.

Aucune émission automatique de document financier : le crédit calculé reste
``a_emettre`` tant qu'un humain n'a pas tranché (``sla_credit_statut``)."""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.roles.models import Role

from core.sla import (
    SlaCreditPolicy, SlaSnapshot, credit_pct_pour_uptime, generer_snapshot_societe,
    politique_active,
)

User = get_user_model()


class CreditPctPourUptimeTest(TestCase):
    def test_worst_crossed_threshold_wins(self):
        paliers = [
            {'seuil_uptime_pct': 99.5, 'credit_pct_facture': 5},
            {'seuil_uptime_pct': 99.0, 'credit_pct_facture': 10},
            {'seuil_uptime_pct': 95.0, 'credit_pct_facture': 25},
        ]
        self.assertEqual(credit_pct_pour_uptime(98.0, paliers), 10)
        self.assertEqual(credit_pct_pour_uptime(94.0, paliers), 25)
        self.assertEqual(credit_pct_pour_uptime(99.9, paliers), 0)

    def test_empty_paliers_never_crashes(self):
        self.assertEqual(credit_pct_pour_uptime(50.0, []), 0)
        self.assertEqual(credit_pct_pour_uptime(50.0, None), 0)


class PolitiqueActiveTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs4')

    def test_defaults_to_system_policy_marked_a_valider(self):
        policy = politique_active(self.company)
        self.assertFalse(policy.valide)
        self.assertIsNone(policy.company_id)

    def test_company_override_takes_precedence(self):
        SlaCreditPolicy.objects.create(
            company=self.company,
            paliers=[{'seuil_uptime_pct': 99.99, 'credit_pct_facture': 50}],
            valide=True)
        policy = politique_active(self.company)
        self.assertEqual(policy.company_id, self.company.id)
        self.assertTrue(policy.valide)


class GenererSnapshotCreditTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs4b')

    def test_below_threshold_computes_credit_a_emettre(self):
        with mock.patch('core.sla.uptime_pct_periode', return_value=94.0), \
                mock.patch('core.sla.montant_facture_mois', return_value=10000.0):
            snap = generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        self.assertEqual(snap.credit_du_pct, 25)
        self.assertEqual(snap.credit_du_montant, 2500.0)
        self.assertEqual(snap.credit_statut, SlaSnapshot.CreditStatut.A_EMETTRE)

    def test_above_threshold_is_non_applicable(self):
        with mock.patch('core.sla.uptime_pct_periode', return_value=99.99):
            snap = generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        self.assertIsNone(snap.credit_du_pct)
        self.assertEqual(snap.credit_statut, SlaSnapshot.CreditStatut.NON_APPLICABLE)

    def test_regenerating_never_overwrites_a_human_decision(self):
        with mock.patch('core.sla.uptime_pct_periode', return_value=94.0), \
                mock.patch('core.sla.montant_facture_mois', return_value=10000.0):
            snap = generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        snap.credit_statut = SlaSnapshot.CreditStatut.EMIS
        snap.save(update_fields=['credit_statut'])

        with mock.patch('core.sla.uptime_pct_periode', return_value=94.0), \
                mock.patch('core.sla.montant_facture_mois', return_value=99999.0):
            snap2 = generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        self.assertEqual(snap2.credit_statut, SlaSnapshot.CreditStatut.EMIS)
        # Le montant déjà émis n'est pas recalculé sur un nouveau chiffre.
        self.assertEqual(snap2.credit_du_montant, snap.credit_du_montant)


class MontantFactureMoisTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs4c')

    def test_reads_real_montant_ttc_from_facturation(self):
        # Résolus par nom (jamais un import statique d'apps.crm/apps.
        # facturation) : core reste une couche de base même en test (AUD422,
        # ".importlinter").
        from django.apps import apps as django_apps
        Client = django_apps.get_model('crm', 'Client')
        Facture = django_apps.get_model('facturation', 'Facture')

        client_obj = Client.objects.create(
            company=self.company, nom='Test', prenom='Client',
            email='c@example.com', telephone='+212600000000',
            adresse='Casablanca')
        Facture.objects.create(
            company=self.company, reference='FA-NTOBS4-1', client=client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ttc=Decimal('5000.00'),
        )
        from core.sla import montant_facture_mois
        periode = datetime.date.today().replace(day=1)
        total = montant_facture_mois(self.company, periode)
        self.assertEqual(total, 5000.0)


class SlaCreditsDusEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs4d')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial')
        self.directeur = User.objects.create_user(
            'directeur4', password='x', company=self.company,
            role=self.role_directeur)
        self.commercial = User.objects.create_user(
            'commercial4', password='x', company=self.company,
            role=self.role_commercial)
        with mock.patch('core.sla.uptime_pct_periode', return_value=94.0), \
                mock.patch('core.sla.montant_facture_mois', return_value=1000.0):
            self.snap = generer_snapshot_societe(
                self.company, datetime.date(2026, 6, 1))

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_directeur_sees_credits_dus(self):
        resp = self._client(self.directeur).get('/api/django/core/sla/credits/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_non_directeur_forbidden(self):
        resp = self._client(self.commercial).get('/api/django/core/sla/credits/')
        self.assertEqual(resp.status_code, 403)

    def test_marking_emis_never_creates_a_financial_document(self):
        url = f'/api/django/core/sla/credits/{self.snap.pk}/statut/'
        resp = self._client(self.directeur).post(url, {'statut': 'emis'})
        self.assertEqual(resp.status_code, 200)
        self.snap.refresh_from_db()
        self.assertEqual(self.snap.credit_statut, SlaSnapshot.CreditStatut.EMIS)
        # Résolu par nom (jamais un import statique d'apps.facturation).
        from django.apps import apps as django_apps
        Avoir = django_apps.get_model('facturation', 'Avoir')
        self.assertEqual(Avoir.objects.filter(company=self.company).count(), 0)
