"""U3-900 (fondateur 29/08/2026) — retrait de ``panneaux_par_900mad``.

Le réglage « panneaux par tranche de 900 MAD » ne pilotait plus aucun calcul
depuis le retrait de la règle de dimensionnement `estimerPanneaux` (backend +
écran générateur, PR #577). Le champ modèle est supprimé
(migration 0080_remove_companyprofile_panneaux_par_900mad) : on vérifie que
l'ancienne clé, envoyée par un client pas encore rafraîchi, est simplement
ignorée par ``CompanyProfileSerializer`` (fields='__all__' ne connaît plus ce
nom de champ) — ni sauvegardée, ni renvoyée, ni source d'erreur 400."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import CompanyProfile

User = get_user_model()

UPDATE_URL = '/api/django/parametres/update/'


class TestPanneauxPar900MadRemoved(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='u3-900-co', defaults={'nom': 'U3-900 Co'})[0]
        self.admin = User.objects.create_user(
            username='u3_900_admin', password='x', role_legacy='admin',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.api = api

    def test_model_has_no_such_field(self):
        field_names = {f.name for f in CompanyProfile._meta.get_fields()}
        self.assertNotIn('panneaux_par_900mad', field_names)

    def test_legacy_key_is_ignored_not_rejected(self):
        resp = self.api.patch(UPDATE_URL, {
            'panneaux_par_900mad': 12,
            'rendement_global': '0.85',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('panneaux_par_900mad', resp.data)
        self.assertEqual(str(resp.data['rendement_global']), '0.850')

    def test_legacy_key_not_persisted(self):
        self.api.patch(
            UPDATE_URL, {'panneaux_par_900mad': 12}, format='json')
        profile = CompanyProfile.objects.get(company=self.company)
        self.assertFalse(hasattr(profile, 'panneaux_par_900mad'))
