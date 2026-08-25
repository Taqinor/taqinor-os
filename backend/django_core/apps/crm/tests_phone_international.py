"""25/08/2026 — LANE NUMÉROS INTERNATIONAUX (ordre fondateur).

Avant cette date, `LeadSerializer.validate_telephone/validate_whatsapp`
déléguaient à `apps.ventes.utils.phone.normalize_ma_phone`, qui FORÇAIT un
préfixe '212' sur (quasi) tout ce qui n'était pas déjà marocain — un numéro
étranger posté à l'API (ex. `+33612345678`) ressortait donc CORROMPU
(`212336…`) au lieu d'être conservé tel quel. `normalize_ma_phone` renvoie
désormais None pour un numéro non reconnaissable comme marocain, donc le
`or value` de `_canonical_phone` (crm/serializers.py) garde la saisie brute.

Ces tests échouaient sur `main` avant le correctif de `phone.py` (25/08/2026)
et passent depuis.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead

User = get_user_model()


def make_company(slug='phone-intl-co', nom='Phone Intl Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestLeadForeignPhoneSurvivesApiWrite(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='phone_intl_user', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.api = make_api(self.user)

    def test_create_keeps_foreign_telephone_exactly_as_typed(self):
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Diaspora', 'telephone': '+33612345678',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['telephone'], '+33612345678')
        lead = Lead.objects.get(nom='Diaspora')
        self.assertEqual(lead.telephone, '+33612345678')

    def test_create_keeps_foreign_whatsapp_exactly_as_typed(self):
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Diaspora WA', 'whatsapp': '+34600123456',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['whatsapp'], '+34600123456')
        lead = Lead.objects.get(nom='Diaspora WA')
        self.assertEqual(lead.whatsapp, '+34600123456')

    def test_patch_of_existing_lead_keeps_foreign_phone_as_typed(self):
        lead = Lead.objects.create(company=self.company, nom='Existant')
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'telephone': '+33 6 12 34 56 78'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['telephone'], '+33 6 12 34 56 78')
        lead.refresh_from_db()
        self.assertEqual(lead.telephone, '+33 6 12 34 56 78')

    def test_moroccan_phone_is_still_canonicalized(self):
        # Comportement historique préservé : un numéro marocain reconnu
        # continue d'être canonicalisé (jamais de régression sur ce chemin).
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Marocain', 'telephone': '0612345678',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['telephone'], '212612345678')
