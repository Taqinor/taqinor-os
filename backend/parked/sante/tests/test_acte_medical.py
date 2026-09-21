"""NTSAN7 — Nomenclature des actes `ActeMedical` : soft-disable (jamais de
suppression physique une fois utilisé — la garde de suppression au sens
strict est complétée dans `test_acte_realise.py`, NTSAN10)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import ActeMedical

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ActeMedicalApiTests(TestCase):
    BASE = '/api/django/sante/actes-medicaux/'

    def setUp(self):
        self.company = make_company('sante-acte-co', 'Clinique Acte')
        self.user = make_user(self.company, 'sante-acte')

    def test_desactiver_ne_supprime_pas(self):
        acte = ActeMedical.objects.create(
            company=self.company, libelle='Consultation générale',
            tarif_base_ttc='150.00')

        api = auth(self.user)
        resp = api.post(f'{self.BASE}{acte.id}/desactiver/')

        self.assertEqual(resp.status_code, 200, resp.data)
        acte.refresh_from_db()
        self.assertFalse(acte.actif)
        self.assertTrue(ActeMedical.objects.filter(pk=acte.pk).exists())

    def test_reactiver(self):
        acte = ActeMedical.objects.create(
            company=self.company, libelle='Radio', actif=False)

        api = auth(self.user)
        resp = api.post(f'{self.BASE}{acte.id}/activer/')

        self.assertEqual(resp.status_code, 200, resp.data)
        acte.refresh_from_db()
        self.assertTrue(acte.actif)
