"""NTRET9 — programme de fidélité par points : crédit automatique sur vente
validée (signal ``core.events.vente_validee``), isolation multi-tenant."""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.fidelite.models import (
    CompteFidelite, MouvementFidelite, ProgrammeFidelite,
)
from apps.fidelite.services import crediter_points_pour_vente
from authentication.models import Company
from core.events import vente_validee


def _company(nom='Société Test'):
    return Company.objects.create(nom=nom)


def _client(company, nom='Client Test'):
    return Client.objects.create(company=company, nom=nom)


class CrediterPointsPourVenteTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.client_crm = _client(self.company)
        self.programme = ProgrammeFidelite.objects.create(
            company=self.company, actif=True,
            points_par_mad=Decimal('1.00'))

    def test_credite_points_exacts_et_cree_compte(self):
        mouvement = crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('250.00'), source_type='vente_comptoir',
            source_id=42)

        self.assertIsNotNone(mouvement)
        self.assertEqual(mouvement.points, 250)
        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        self.assertEqual(compte.solde_points, 250)
        self.assertEqual(
            MouvementFidelite.objects.filter(compte=compte).count(), 1)

    def test_deuxieme_vente_cumule_sur_le_meme_compte(self):
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('100.00'), source_type='facture', source_id=1)
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('50.00'), source_type='facture', source_id=2)

        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        self.assertEqual(compte.solde_points, 150)
        self.assertEqual(
            MouvementFidelite.objects.filter(compte=compte).count(), 2)

    def test_programme_desactive_aucun_mouvement(self):
        self.programme.actif = False
        self.programme.save(update_fields=['actif'])

        mouvement = crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('300.00'), source_type='vente_comptoir')

        self.assertIsNone(mouvement)
        self.assertFalse(
            CompteFidelite.objects.filter(company=self.company).exists())

    def test_aucun_programme_aucun_mouvement(self):
        self.programme.delete()

        mouvement = crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('300.00'), source_type='vente_comptoir')

        self.assertIsNone(mouvement)

    def test_client_absent_no_op_jamais_bloquant(self):
        mouvement = crediter_points_pour_vente(
            company=self.company, client=None,
            montant_ttc=Decimal('300.00'), source_type='vente_comptoir')
        self.assertIsNone(mouvement)

    def test_montant_zero_no_op(self):
        mouvement = crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('0'), source_type='vente_comptoir')
        self.assertIsNone(mouvement)

    def test_isolation_multi_tenant(self):
        autre_company = _company('Autre Société')
        autre_client = _client(autre_company, 'Autre Client')
        ProgrammeFidelite.objects.create(
            company=autre_company, actif=True, points_par_mad=Decimal('1.00'))

        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('100.00'), source_type='facture')
        crediter_points_pour_vente(
            company=autre_company, client=autre_client,
            montant_ttc=Decimal('999.00'), source_type='facture')

        compte_1 = CompteFidelite.objects.get(company=self.company)
        compte_2 = CompteFidelite.objects.get(company=autre_company)
        self.assertEqual(compte_1.solde_points, 100)
        self.assertEqual(compte_2.solde_points, 999)
        self.assertNotEqual(compte_1.client_id, compte_2.client_id)


class VenteValideeSignalTests(TestCase):
    """L'événement `vente_validee` (core.events) est posé par NTRET9 mais PAS
    ENCORE ÉMIS par apps.pos/apps.ventes (hors périmètre SUPPLY) — l'abonné
    `fidelite.receivers` est testé en envoyant le signal directement."""

    def setUp(self):
        self.company = _company()
        self.client_crm = _client(self.company)
        ProgrammeFidelite.objects.create(
            company=self.company, actif=True, points_par_mad=Decimal('2.00'))

    def test_signal_declenche_le_credit_via_le_recepteur(self):
        vente_validee.send(
            sender=None, company=self.company, client=self.client_crm,
            montant_ttc=Decimal('100.00'), source_type='vente_comptoir',
            source_id=7, user=None)

        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        self.assertEqual(compte.solde_points, 200)

    def test_signal_avec_montant_invalide_ne_leve_jamais(self):
        # Best-effort : un abonné qui échouerait ne doit jamais remonter
        # d'exception à l'émetteur (une vente ne doit jamais planter à cause
        # de la fidélité).
        vente_validee.send(
            sender=None, company=self.company, client=self.client_crm,
            montant_ttc=None, source_type='vente_comptoir', source_id=1,
            user=None)
        self.assertFalse(
            CompteFidelite.objects.filter(company=self.company).exists())
