"""NTP2P47 — KPI notes de frais & per-diem dans ``apps.reporting``.

Le module est un AGRÉGATEUR pur au-dessus des 4 sélecteurs
``apps.frais.selectors`` (déjà testés isolément dans
``apps/frais/tests/test_ntp2p47_kpi_selectors.py``) : ces tests vérifient
la COMBINAISON (champs exposés, garde société, endpoint), pas la logique
d'agrégation elle-même."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting.frais_kpi import dashboard_frais_kpi
from authentication.models import Company

User = get_user_model()

FAUX_CATEGORIES = [
    {'categorie': 'carburant', 'categorie_display': 'Carburant',
     'montant_total': 100},
]
FAUX_TOP = [{'employe_id': 1, 'employe_nom': 'Amine B.', 'montant_total': 350}]
FAUX_DESTINATIONS = [{'destination': 'Rabat', 'montant_total': 450}]


class DashboardFraisKpiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTP2P47 SA', slug='ntp2p47-sa')

    @patch('apps.frais.selectors.total_per_diem_par_destination',
           return_value=FAUX_DESTINATIONS)
    @patch('apps.frais.selectors.delai_moyen_depense_remboursement_jours',
           return_value=14.0)
    @patch('apps.frais.selectors.top_employes_par_montant_notes_frais',
           return_value=FAUX_TOP)
    @patch('apps.frais.selectors.total_rembourse_par_categorie',
           return_value=FAUX_CATEGORIES)
    def test_agrege_les_quatre_selecteurs_sans_les_alterer(
            self, _mock_cat, _mock_top, _mock_delai, _mock_dest):
        resultat = dashboard_frais_kpi(self.company)
        self.assertEqual(
            resultat['total_rembourse_par_categorie'], FAUX_CATEGORIES)
        self.assertEqual(resultat['top_employes'], FAUX_TOP)
        self.assertEqual(
            resultat['delai_moyen_depense_remboursement_jours'], 14.0)
        self.assertEqual(
            resultat['total_per_diem_par_destination'], FAUX_DESTINATIONS)


class KpiFraisEndpointTests(TestCase):
    URL = '/api/django/reporting/frais/kpi/'

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTP2P47 EP SA', slug='ntp2p47-ep-sa')
        cls.admin = User.objects.create_user(
            username='ntp2p47_admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.normal = User.objects.create_user(
            username='ntp2p47_normal', password='x', company=cls.company,
            role_legacy=User.ROLE_NORMAL)

    def _client_for(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def test_endpoint_reserve_responsable_admin(self):
        resp = self._client_for(self.admin).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('total_rembourse_par_categorie', resp.data)
        self.assertIn('top_employes', resp.data)
        self.assertIn('delai_moyen_depense_remboursement_jours', resp.data)
        self.assertIn('total_per_diem_par_destination', resp.data)

    def test_endpoint_refuse_role_normal(self):
        resp = self._client_for(self.normal).get(self.URL)
        self.assertEqual(resp.status_code, 403)
