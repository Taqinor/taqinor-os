"""AFAC55 (C-AFAC-048) — les actions de facturation et le viewset des
paiements passent par la portée de ``FactureViewSet`` : ``bulk`` et
``encaissement-groupe`` résolvent leurs factures par ``get_queryset()``,
``PaiementViewSet`` borne par ``created_by`` / ``facture__created_by``,
``ventiler`` et ``paiement-avec-retenue`` résolvent la facture dans ce même
périmètre.

Rejoue les sondes FEVT-3 / FEVT-3b (bulk relancer 200 `ok:true`, e-mail
« Votre facture … » parti, `GET paiements/` le liste, encaissement groupé
201). APIClient, rôles réels (portée équipe sans superviseur commun),
e-mail locmem, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_portee_actions_paiements"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()
BASE = '/api/django/ventes/factures/'
PAIEMENTS = '/api/django/ventes/paiements/'


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PorteeActionsPaiementsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Client
        from apps.roles.models import Role
        from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
        from apps.ventes.models import Facture, Paiement
        from authentication.models import Company
        cls.company = Company.objects.create(nom='AFAC55', slug='afac55-co')
        role_equipe = Role.objects.create(
            company=cls.company, nom='Commercial',
            permissions=RESPONSABLE_PERMISSIONS + [
                'encaisser', 'records_scope_equipe'],
            est_systeme=False)
        cls.proprio = User.objects.create_user(
            username='afac55_proprio', password='x', role=role_equipe,
            role_legacy='responsable', company=cls.company)
        cls.autre = User.objects.create_user(
            username='afac55_autre', password='x', role=role_equipe,
            role_legacy='responsable', company=cls.company)
        cls.admin = User.objects.create_user(
            username='afac55_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='AFAC55',
            email='afac55@example.invalid')
        cls.facture = Facture.objects.create(
            company=cls.company, reference='FAC-AFAC55-0001',
            client=cls.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('10000'),
            montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'),
            created_by=cls.proprio)
        cls.paiement = Paiement.objects.create(
            company=cls.company, facture=cls.facture,
            montant=Decimal('1000'), date_paiement=date(2026, 10, 1),
            mode=Paiement.Mode.VIREMENT, created_by=cls.proprio)

    def _api(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _ids(self, resp):
        corps = resp.data
        rows = corps.get('results', corps) if isinstance(corps, dict) else corps
        return {row['id'] for row in rows}

    def test_bulk_relancer_hors_portee(self):
        from apps.ventes.models import RelanceLog
        r = self._api(self.autre).post(f'{BASE}bulk/', {
            'action': 'relancer', 'ids': [self.facture.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data[self.facture.id]['ok'])
        self.assertEqual(r.data[self.facture.id]['detail'], 'Introuvable.')
        self.assertFalse(
            RelanceLog.objects.filter(facture=self.facture).exists())

    def test_bulk_envoyer_email_hors_portee(self):
        from apps.ventes.models import EmailLog
        r = self._api(self.autre).post(f'{BASE}bulk/', {
            'action': 'envoyer-email', 'ids': [self.facture.id]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data[self.facture.id]['ok'])
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EmailLog.objects.filter(
            facture=self.facture).exists())

    def test_encaissement_groupe_hors_portee(self):
        from apps.ventes.models import Paiement
        avant = Paiement.objects.filter(company=self.company).count()
        r = self._api(self.autre).post(f'{BASE}encaissement-groupe/', {
            'client': self.client_obj.id, 'montant': '500',
            'mode': 'virement', 'factures': [self.facture.id]},
            format='json')
        self.assertIn(r.status_code, (400, 404), r.data)
        self.assertEqual(
            Paiement.objects.filter(company=self.company).count(), avant)

    def test_paiements_liste_detail_recu_hors_portee(self):
        api = self._api(self.autre)
        liste = api.get(PAIEMENTS)
        self.assertEqual(liste.status_code, 200)
        self.assertNotIn(self.paiement.id, self._ids(liste))
        self.assertEqual(
            api.get(f'{PAIEMENTS}{self.paiement.id}/').status_code, 404)
        self.assertEqual(
            api.get(f'{PAIEMENTS}{self.paiement.id}/recu-pdf/').status_code,
            404)

    def test_ventiler_et_retenue_hors_portee(self):
        from apps.ventes.models import AffectationPaiement, Paiement
        from apps.ventes.services import enregistrer_avance
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('300'), date_paiement=date(2026, 10, 2),
            mode='virement', created_by=self.autre)
        api = self._api(self.autre)
        r = api.post(f'{PAIEMENTS}{avance.id}/ventiler/', {
            'facture': self.facture.id, 'montant': '300'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['detail'], 'Facture introuvable.')
        self.assertFalse(AffectationPaiement.objects.filter(
            facture=self.facture).exists())
        avant = Paiement.objects.filter(facture=self.facture).count()
        r = api.post(
            f'{PAIEMENTS}factures/{self.facture.id}/paiement-avec-retenue/',
            {'montant': '1000', 'date_paiement': '2026-10-02',
             'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '75'},
            format='json')
        self.assertEqual(r.status_code, 404, r.data)
        self.assertEqual(r.data['detail'], 'Facture introuvable.')
        self.assertEqual(
            Paiement.objects.filter(facture=self.facture).count(), avant)

    def test_proprietaire_et_admin_inchanges(self):
        for user in (self.proprio, self.admin):
            api = self._api(user)
            liste = api.get(PAIEMENTS)
            self.assertIn(self.paiement.id, self._ids(liste))
            self.assertEqual(
                api.get(f'{PAIEMENTS}{self.paiement.id}/').status_code, 200)
        r = self._api(self.proprio).post(f'{BASE}bulk/', {
            'action': 'relancer', 'ids': [self.facture.id]}, format='json')
        self.assertTrue(r.data[self.facture.id]['ok'], r.data)
