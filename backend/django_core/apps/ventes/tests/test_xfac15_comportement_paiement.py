"""
XFAC15 — Câblage du scorer de retard de paiement FG365 : score client agrégé
+ date d'encaissement prévue dans le forecast.

Un client historiquement à +20 j voit ses factures projetées à échéance+20
dans le forecast comportemental, le score s'affiche client + recouvrement, le
calcul délègue à ``core/payment_delay.py`` (pas de logique dupliquée), client
sans historique = score neutre.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac15_comportement_paiement -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement
from apps.ventes.selectors import comportement_paiement, date_encaissement_prevue

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac15-co', nom='XFAC15 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac15@example.com'):
    return Client.objects.create(
        company=company, nom='Comportement', prenom='Client',
        email=email, telephone='+212600000063', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC15ComportementPaiementTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac15_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)

    def _paid_facture(self, n, emission_days_ago, paid_days_after_emission):
        emission = timezone.now().date() - timedelta(days=emission_days_ago)
        f = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-{n:04d}',
            client=self.client_obj, statut=Facture.Statut.PAYEE,
            montant_ttc=Decimal('5000'), created_by=self.admin,
        )
        Facture.objects.filter(pk=f.pk).update(date_emission=emission)
        f.refresh_from_db()
        Paiement.objects.create(
            company=self.company, facture=f, montant=Decimal('5000'),
            date_paiement=emission + timedelta(days=paid_days_after_emission),
            mode='virement',
        )
        return f

    def test_no_history_client_gets_neutral_score(self):
        """Client sans facture du tout → score neutre (used_fallback)."""
        result = comportement_paiement(self.client_obj)
        self.assertTrue(result['used_fallback'])
        self.assertIsNone(result['retard_moyen_jours'])
        self.assertEqual(result['nb_factures_historique'], 0)

    def test_client_with_consistent_20_day_delay_history(self):
        """Historique de paiements systématiquement à J+20 → retard moyen
        réel ≈ 20 jours, et une facture ouverte est projetée à échéance+20
        dans le forecast comportemental."""
        for i in range(3):
            self._paid_facture(i, emission_days_ago=60 + i, paid_days_after_emission=20)

        result = comportement_paiement(self.client_obj)
        self.assertEqual(result['retard_moyen_jours'], 20.0)
        self.assertEqual(result['nb_factures_historique'], 3)
        self.assertIn(result['lettre'], ['A', 'B', 'C', 'D', 'E'])

        # Facture ouverte : échéance connue, projection décalée de +20 j.
        echeance = timezone.now().date() + timedelta(days=10)
        ouverte = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0900',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('3000'), created_by=self.admin,
            date_echeance=echeance,
        )
        prevue = date_encaissement_prevue(
            ouverte, result['retard_moyen_jours'])
        self.assertEqual(prevue, echeance + timedelta(days=20))

    def test_score_appears_on_client_badge_endpoint(self):
        r = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/'
            'score-comportement/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('lettre', r.data)
        self.assertIn('score', r.data)

    def test_score_appears_on_relances_list_and_balance_agee(self):
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0910',
            client=self.client_obj, statut=Facture.Statut.EN_RETARD,
            montant_ttc=Decimal('2000'), created_by=self.admin,
            date_echeance=timezone.now().date() - timedelta(days=5),
        )
        r = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(len(r.data) >= 1)
        self.assertIn('score_comportement', r.data[0])

        r2 = self.api.get('/api/django/ventes/balance-agee/')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertTrue(len(r2.data) >= 1)
        self.assertIn('score_comportement', r2.data[0])

    def test_cash_flow_forecast_comportement_mode_shifts_bucket(self):
        """Une facture qui échoit demain (bucket 'cette_semaine' sans mode)
        se décale à un bucket ultérieur en mode comportemental si le client a
        un retard moyen historique important."""
        for i in range(2):
            self._paid_facture(
                100 + i, emission_days_ago=90 + i,
                paid_days_after_emission=45)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0920',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('1000'), created_by=self.admin,
            date_echeance=timezone.now().date() + timedelta(days=1),
        )
        r_theorique = self.api.get('/api/django/ventes/insights/cash-flow/')
        self.assertEqual(r_theorique.status_code, 200, r_theorique.data)
        self.assertEqual(
            r_theorique.data['buckets']['cette_semaine']['count'], 1)

        r_comportement = self.api.get(
            '/api/django/ventes/insights/cash-flow/?mode=comportement')
        self.assertEqual(r_comportement.status_code, 200, r_comportement.data)
        # Décalé de ~45 j → sort du bucket 'cette_semaine'.
        self.assertEqual(
            r_comportement.data['buckets']['cette_semaine']['count'], 0)
