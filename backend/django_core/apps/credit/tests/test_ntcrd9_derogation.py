"""NTCRD9 — dérogation crédit : demande → approbation → lève le hold de
blocage ; approbation réservée Directeur/Administrateur."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.credit.models import DerogationCredit, LimiteCredit
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd9-co', nom='NTCRD9 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD9DerogationTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='ntcrd9_com', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd9@example.com')

    def test_commercial_can_request_derogation(self):
        r = auth(self.commercial).post('/api/django/credit/derogations/', {
            'client': self.client_obj.id, 'montant_demande': '5000',
            'motif': 'Client stratégique, commande urgente.',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        d = DerogationCredit.objects.get(client=self.client_obj)
        self.assertEqual(d.statut, DerogationCredit.Statut.EN_ATTENTE)
        self.assertEqual(d.demandeur_id, self.commercial.id)
        self.assertEqual(d.company_id, self.company.id)

    def test_commercial_cannot_approve(self):
        d = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        r = auth(self.commercial).post(
            f'/api/django/credit/derogations/{d.id}/approuver/')
        self.assertEqual(r.status_code, 403)

    def test_admin_can_approve(self):
        d = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        r = auth(self.admin).post(
            f'/api/django/credit/derogations/{d.id}/approuver/')
        self.assertEqual(r.status_code, 200, r.data)
        d.refresh_from_db()
        self.assertEqual(d.statut, DerogationCredit.Statut.APPROUVEE)
        self.assertIsNotNone(d.valide_jusqu_au)
        self.assertTrue(d.est_valide)

    def test_end_to_end_derogation_lifts_hold(self):
        """Devis bloqué (mode blocage + dépassement) devient autorisé après
        approbation de la dérogation (au niveau du service NTCRD6)."""
        from apps.credit.services import verifier_hold_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        # Avant dérogation : blocage refuse.
        avant = verifier_hold_credit(self.client_obj, Decimal('5000'))
        self.assertFalse(avant['autorise'])
        # Demande + approbation d'une dérogation couvrant le montant.
        d = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        r = auth(self.admin).post(
            f'/api/django/credit/derogations/{d.id}/approuver/')
        self.assertEqual(r.status_code, 200, r.data)
        # Après : autorisé pour ce montant.
        apres = verifier_hold_credit(self.client_obj, Decimal('5000'))
        self.assertTrue(apres['autorise'])

    def test_reject_derogation(self):
        d = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        r = auth(self.admin).post(
            f'/api/django/credit/derogations/{d.id}/rejeter/')
        self.assertEqual(r.status_code, 200, r.data)
        d.refresh_from_db()
        self.assertEqual(d.statut, DerogationCredit.Statut.REJETEE)
        self.assertFalse(d.est_valide)
