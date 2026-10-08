"""APDF24 — ``nom_intervenant`` : jamais l'identifiant ni un e-mail."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.parametres.models import CompanyProfile
from apps.parametres.selectors import nom_intervenant

User = get_user_model()


class NomIntervenantTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(slug='apdf24', nom='Apdf24')
        CompanyProfile.objects.update_or_create(
            company=self.company,
            defaults={'nom': 'TAQINOR Démo (complet)'})

    def test_sans_nom_raison_sociale(self):
        u = User.objects.create_user(
            username='x4.tech@outlook.com', password='x',
            company=self.company)
        self.assertEqual(nom_intervenant(u, self.company),
                         'TAQINOR Démo (complet)')
        self.assertEqual(nom_intervenant(None, self.company), '')

    def test_nom_complet(self):
        u = User.objects.create_user(
            username='omar', password='x', first_name='Omar',
            last_name='Tazi', company=self.company)
        self.assertEqual(nom_intervenant(u, self.company), 'Omar Tazi')

    def test_jamais_username(self):
        u = User.objects.create_user(
            username='x4.tech@outlook.com', password='x',
            company=self.company)
        res = nom_intervenant(u, self.company)
        self.assertNotIn('@', res)
        self.assertNotEqual(res, u.username)
        v = User.objects.create_user(
            username='mail', password='x', first_name='a@b.c',
            company=self.company)
        self.assertNotIn('@', nom_intervenant(v, self.company))
