"""ACRM64 / ACRM67 — routes crm RETIRÉES par la décision fondateur D-ACRM-6
(09/10/2026) : leurs écrans n'existent plus (ou n'ont jamais existé), la route
et son calcul partent avec eux.

Nouveau fichier car : un module unique pour les routes retirées par D-ACRM-6
(partagé entre ACRM64 — famille (i) — et ACRM67 — famille (iv)).

Source réelle : le routeur réel (``/api/django/crm/…``) — aucun mock.
Test-du-test : remettre une action retirée ⇒ son test repasse à 200 et échoue.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Defi, Lead, PointContact
from apps.parametres.models import CompanyProfile

User = get_user_model()

BASE = '/api/django/crm/'


class RoutesRetireesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='Routes retirées', slug='acrm-routes-retirees')
        CompanyProfile.objects.get_or_create(company=cls.company)
        cls.admin = User.objects.create_user(
            username='acrm-rr-admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.commerciale = User.objects.create_user(
            username='acrm-rr-comm', password='x', role_legacy='normal',
            company=cls.company)

    def _get(self, user, chemin):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api.get(BASE + chemin)

    def _assert_404_pour_tous(self, chemin):
        for user in (self.admin, self.commerciale):
            resp = self._get(user, chemin)
            self.assertEqual(resp.status_code, 404, (user.username, chemin))

    # ── ACRM64 — famille (i) : cockpit d'adhérence et tuiles personnelles ──
    def test_kpi_adherence_404(self):
        self._assert_404_pour_tous('relance-etapes/kpi-adherence/')
        self._assert_404_pour_tous('relance-etapes/kpi-adherence/?jours=30')

    def test_mes_stats_404(self):
        self._assert_404_pour_tous('relance-etapes/mes-stats/')

    # ── ACRM67 — famille (iv) : routes sans appelant front ──────────────────
    def _fixture_iv(self):
        import datetime

        from django.utils import timezone
        today = timezone.now().date()
        defi = Defi.objects.create(
            company=self.company, nom='Défi retiré',
            periode_debut=today - datetime.timedelta(days=3),
            periode_fin=today + datetime.timedelta(days=3),
            metrique='nb_leads')
        lead = Lead.objects.create(
            company=self.company, nom='Lead touches', owner=self.admin)
        PointContact.objects.create(
            company=self.company, lead=lead, canal='meta_ads', ordre=1,
            date_contact=timezone.now())
        Client.objects.create(company=self.company, nom='Client démo')
        return defi, lead

    def test_export_defi_404(self):
        defi, _lead = self._fixture_iv()
        self._assert_404_pour_tous(f'defis/{defi.pk}/export-xlsx/')

    def test_attribution_points_contact_404(self):
        _defi, lead = self._fixture_iv()
        self._assert_404_pour_tous(f'points-contact/attribution/?lead={lead.pk}')
        self._assert_404_pour_tous('points-contact/attribution/')

    def test_segments_404(self):
        """Reprend le test d'ACRM44 : CHAQUE valeur acceptée hier (dont
        ``dormants``, qui répondait 500) répond 404."""
        self._fixture_iv()
        for segment in ('top', 'sans_devis', 'a_recontacter', 'dormants', ''):
            with self.subTest(segment=segment):
                self._assert_404_pour_tous(f'clients/segments/?segment={segment}')

    def test_les_survivants_repondent_comme_avant(self):
        """L'attribution d'un lead et les comptes dormants restent servis."""
        _defi, lead = self._fixture_iv()
        resp = self._get(self.admin, f'leads/{lead.pk}/points-contact/')
        self.assertEqual(resp.status_code, 200, resp.content[:200])
        self.assertEqual(resp.data['count'], 1)
        resp = self._get(self.admin, 'clients/dormants/')
        self.assertEqual(resp.status_code, 200, resp.content[:200])

    def test_les_autres_lectures_du_cockpit_repondent_comme_avant(self):
        for chemin in ('relance-etapes/', 'relance-etapes/controle/?jours=7',
                       'relance-etapes/chaine-commerciale/'):
            resp = self._get(self.admin, chemin)
            self.assertEqual(resp.status_code, 200, (chemin, resp.content[:200]))
