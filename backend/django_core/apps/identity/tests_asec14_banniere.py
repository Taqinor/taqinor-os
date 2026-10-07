"""ASEC14 — la bannière de connexion ne dépend plus du ``username`` reçu.

Elle est celle de la société résolue par l'HÔTE (``TenantTheme.domaine``),
sinon une bannière plateforme neutre (vide) — jamais celle d'une société
désignée par un nom d'utilisateur, jamais ``CompanyProfile pk=1``.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.parametres.models_company import CompanyProfile
from authentication.models import Company, CustomUser
from core.models import TenantTheme

URL = '/api/django/identity/login-banner/'
HOTE_A = 'societe-a.example'


@override_settings(ALLOWED_HOSTS=[HOTE_A, 'testserver'])
class BanniereNeutreTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='ASEC14 A', slug='asec14-a')
        CompanyProfile.objects.update_or_create(
            company=self.co_a,
            defaults={'login_banner_text': 'Mention de la société A.'})
        TenantTheme.objects.create(company=self.co_a, domaine=HOTE_A)
        CustomUser.objects.create_user(
            username='asec14_a', password='x', company=self.co_a)

    def test_username_autre_societe_banniere_neutre(self):
        # Hôte plateforme (non rattaché) + username d'un compte de A : neutre.
        resp = APIClient().get(URL, {'username': 'asec14_a'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['login_banner_text'], '')
        # Hôte de A : la bannière de A, quel que soit le username.
        resp = APIClient(HTTP_HOST=HOTE_A).get(URL, {'username': 'inconnu'})
        self.assertEqual(resp.data['login_banner_text'],
                         'Mention de la société A.')

    def test_jamais_profil_pk1(self):
        if not CompanyProfile.objects.filter(pk=1).exists():
            co = Company.objects.create(nom='ASEC14 pk1', slug='asec14-pk1')
            CompanyProfile.objects.create(
                pk=1, company=co, login_banner_text='Bannière pk=1.')
        else:
            CompanyProfile.objects.filter(pk=1).update(
                login_banner_text='Bannière pk=1.')
        resp = APIClient().get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['login_banner_text'], '')
