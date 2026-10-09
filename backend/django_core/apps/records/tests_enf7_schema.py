"""ENF7 — contrat OpenAPI exact de ``records`` : statuts et parseurs réels.

* une cible incomplète (``model`` sans ``id``) ou introuvable est un 404, pas un
  400 (le corps est conforme au schéma) ;
* seul le dépôt de pièce jointe est multipart ; le reste n'accepte que le JSON
  (décision D2) ;
* le schéma énumère les cibles autorisées (``CibleModelField``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import ActivityType
from .openapi import CibleModelFieldExtension, cibles_autorisees

User = get_user_model()


class Enf7ContratTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ENF7 Records')
        self.user = User.objects.create_user(
            username='enf7_rec', password='pw', company=self.company,
            role_legacy='admin')
        self.type = ActivityType.objects.create(
            company=self.company, nom='Appel', icone='📞')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_cible_incomplete_est_404(self):
        resp = self.api.post('/api/django/records/activities/', {
            'model': 'crm.lead', 'activity_type': self.type.id,
        }, format='json')
        self.assertEqual(resp.status_code, 404, getattr(resp, 'data', resp))
        resp = self.api.post('/api/django/records/activities/', {
            'id': 5, 'activity_type': self.type.id,
        }, format='json')
        self.assertEqual(resp.status_code, 404, getattr(resp, 'data', resp))

    def test_type_de_cible_non_autorise_reste_400(self):
        resp = self.api.post('/api/django/records/comments/', {
            'model': 'auth.user', 'id': 1, 'body': 'x',
        }, format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))

    def test_json_seul_hors_depot_de_fichier(self):
        resp = self.api.post(
            '/api/django/records/tags/', {'nom': 'T'}, format='multipart')
        self.assertEqual(resp.status_code, 415, getattr(resp, 'data', resp))
        resp = self.api.post(
            '/api/django/records/tags/', {'nom': 'T'}, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))

    def test_enum_des_cibles_dans_le_schema(self):
        cibles = cibles_autorisees()
        self.assertIn('crm.lead', cibles)
        schema = CibleModelFieldExtension(None).map_serializer_field(
            None, 'request')
        self.assertEqual(schema['enum'], cibles)
