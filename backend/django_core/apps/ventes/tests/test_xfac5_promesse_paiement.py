"""
XFAC5 — Promesse de paiement (promise-to-pay) + pause de relance à expiration.

Créer une promesse stoppe la relance planifiée, la date passée impayée
re-active + marque rompue, la balance des impayés affiche promesses en
cours/rompues, tests (idempotence du job, scoping).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac5_promesse_paiement -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, PromessePaiement

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac5-co', nom='XFAC5 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac5@example.com'):
    return Client.objects.create(
        company=company, nom='Promesse', prenom='Client',
        email=email, telephone='+212600000053', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC5PromessePaiementTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac5_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        today = timezone.now().date()
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal('5000'), created_by=self.admin,
            date_echeance=today - timedelta(days=20),
            prochaine_relance=today,
        )

    def test_creating_promise_suspends_scheduled_relance(self):
        date_promise = (timezone.now().date() + timedelta(days=10)).isoformat()
        r = self.api.post('/api/django/ventes/promesses-paiement/', {
            'facture': self.facture.id, 'montant_promis': '5000',
            'date_promise': date_promise, 'note': 'Client promet le 15',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertIsNotNone(self.facture.exclu_relances_jusquau)
        self.assertEqual(
            self.facture.exclu_relances_jusquau.isoformat(), date_promise)

        from apps.ventes.scheduled import relance_reminders
        sent = relance_reminders()
        self.assertEqual(sent, 0)  # relance suspendue, rien n'est envoyé

    def test_expired_unpaid_promise_marked_rompue_and_resumes_relance(self):
        promesse = PromessePaiement.objects.create(
            company=self.company, facture=self.facture,
            montant_promis=Decimal('5000'),
            date_promise=timezone.now().date() - timedelta(days=1),
            statut=PromessePaiement.Statut.EN_COURS,
        )
        self.facture.exclu_relances_jusquau = promesse.date_promise
        self.facture.save(update_fields=['exclu_relances_jusquau'])

        from apps.ventes.scheduled import _check_promesses_expirees, \
            casablanca_today
        rompues = _check_promesses_expirees(casablanca_today())
        self.assertEqual(rompues, 1)
        promesse.refresh_from_db()
        self.assertEqual(promesse.statut, PromessePaiement.Statut.ROMPUE)
        self.facture.refresh_from_db()
        self.assertIsNone(self.facture.exclu_relances_jusquau)

    def test_idempotent_job_does_not_re_break_already_rompue(self):
        promesse = PromessePaiement.objects.create(
            company=self.company, facture=self.facture,
            montant_promis=Decimal('5000'),
            date_promise=timezone.now().date() - timedelta(days=5),
            statut=PromessePaiement.Statut.ROMPUE,
        )
        from apps.ventes.scheduled import _check_promesses_expirees, \
            casablanca_today
        rompues = _check_promesses_expirees(casablanca_today())
        self.assertEqual(rompues, 0)
        promesse.refresh_from_db()
        self.assertEqual(promesse.statut, PromessePaiement.Statut.ROMPUE)

    def test_relances_list_shows_promesse_en_cours(self):
        PromessePaiement.objects.create(
            company=self.company, facture=self.facture,
            montant_promis=Decimal('5000'),
            date_promise=timezone.now().date() + timedelta(days=10),
            statut=PromessePaiement.Statut.EN_COURS,
        )
        r = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.data if x['id'] == self.facture.id)
        self.assertIsNotNone(row['promesse'])
        self.assertEqual(row['promesse']['statut'], 'en_cours')

    def test_scoping_cross_company_promesse_rejected(self):
        other_company = make_company(slug='xfac5-other', nom='Other Co')
        other_admin = User.objects.create_user(
            username='xfac5_other_admin', password='x', role_legacy='admin',
            company=other_company,
        )
        other_api = auth(other_admin)
        r = other_api.post('/api/django/ventes/promesses-paiement/', {
            'facture': self.facture.id, 'montant_promis': '5000',
            'date_promise': timezone.now().date().isoformat(),
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_full_payment_closes_promise_as_tenue(self):
        promesse = PromessePaiement.objects.create(
            company=self.company, facture=self.facture,
            montant_promis=Decimal('5000'),
            date_promise=timezone.now().date() + timedelta(days=5),
            statut=PromessePaiement.Statut.EN_COURS,
        )
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '5000', 'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        promesse.refresh_from_db()
        self.assertEqual(promesse.statut, PromessePaiement.Statut.TENUE)
