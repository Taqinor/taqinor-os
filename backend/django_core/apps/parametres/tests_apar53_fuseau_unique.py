"""APAR53 — le fuseau de la société est UN réglage (C-APAR-042) :
``core.tz_display`` lit ``CompanyProfile.fuseau_horaire`` (Paramètres ›
Localisation) et ``timezone_affichage`` n'est plus inscriptible par le PATCH
générique du profil (il reste servi en lecture).
"""
import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models_company import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company
from core.tz_display import to_company_tz

User = get_user_model()
URL_PATCH = '/api/django/parametres/update/'


class FuseauUniqueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR53', slug='apar53')
        profil = CompanyProfile.get(company=self.company)
        profil.fuseau_horaire = 'Africa/Dakar'
        profil.timezone_affichage = 'Africa/Casablanca'
        profil.save()
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.user = User.objects.create_user(
            username='apar53', password='x', role=role, company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))

    def test_to_company_tz_suit_fuseau_horaire(self):
        dt = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo('UTC'))
        self.assertEqual(str(to_company_tz(dt, self.company).tzinfo),
                         'Africa/Dakar')

    def test_reglage_localisation_change_l_affichage(self):
        r = self.api.patch(URL_PATCH, {'fuseau_horaire': 'Europe/Paris'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        dt = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo('UTC'))
        self.assertEqual(str(to_company_tz(dt, self.company).tzinfo),
                         'Europe/Paris')

    def test_timezone_affichage_lecture_seule(self):
        r = self.api.patch(URL_PATCH, {'timezone_affichage': 'n importe quoi'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['timezone_affichage'], 'Africa/Casablanca')
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertEqual(profil.timezone_affichage, 'Africa/Casablanca')

    def test_fuseau_invalide_refuse(self):
        r = self.api.patch(URL_PATCH, {'fuseau_horaire': 'Pas/UnFuseau'},
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
