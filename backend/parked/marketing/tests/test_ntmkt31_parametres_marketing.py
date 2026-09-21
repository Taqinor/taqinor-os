"""NTMKT31 — Réglages tenant « Marketing » dans Paramètres.

Singleton société additif : une société sans ligne ``ParametresMarketing``
garde le comportement actuel (plafond désactivé = jamais bloquant).
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne, EnvoiCampagne, ParametresMarketing

User = get_user_model()


class ParametresMarketingServiceTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt31', nom='NTMKT31')

    def test_get_or_create_singleton(self):
        p1 = mkt_services.parametres_marketing_pour(self.co)
        p2 = mkt_services.parametres_marketing_pour(self.co)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(ParametresMarketing.objects.filter(
            company=self.co).count(), 1)

    def test_plafond_desactive_par_defaut_jamais_bloquant(self):
        self.assertFalse(mkt_services.plafond_envois_atteint(self.co))

    def test_plafond_atteint_bloque(self):
        parametres = mkt_services.parametres_marketing_pour(self.co)
        parametres.plafond_envois_jour = 2
        parametres.save(update_fields=['plafond_envois_jour'])
        campagne = Campagne.objects.create(company=self.co, nom='C')
        aujourdhui = timezone.now()
        for i in range(2):
            EnvoiCampagne.objects.create(
                company=self.co, campagne=campagne,
                destinataire=f'{i}@b.ma', envoye_le=aujourdhui)
        self.assertTrue(mkt_services.plafond_envois_atteint(
            self.co, aujourdhui=aujourdhui.date()))

    def test_plafond_sous_le_seuil_ne_bloque_pas(self):
        parametres = mkt_services.parametres_marketing_pour(self.co)
        parametres.plafond_envois_jour = 5
        parametres.save(update_fields=['plafond_envois_jour'])
        campagne = Campagne.objects.create(company=self.co, nom='C')
        EnvoiCampagne.objects.create(
            company=self.co, campagne=campagne, destinataire='a@b.ma',
            envoye_le=timezone.now())
        self.assertFalse(mkt_services.plafond_envois_atteint(self.co))


class ParametresMarketingEndpointTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt31b', nom='NTMKT31b')
        self.user = User.objects.create_user(
            username='ntmkt31_user', password='x', role_legacy='responsable',
            company=self.co)

    def test_endpoint_exige_une_authentification(self):
        res = self.client.get('/api/django/marketing/parametres/')
        self.assertIn(res.status_code, (401, 403))

    def test_get_puis_maj(self):
        # JWT (cookie ou Bearer, CookieJWTAuthentication) — pas de session
        # Django, donc ``force_login`` n'authentifie pas ces endpoints DRF.
        auth = {'HTTP_AUTHORIZATION': f'Bearer {AccessToken.for_user(self.user)}'}
        res = self.client.get('/api/django/marketing/parametres/', **auth)
        self.assertEqual(res.status_code, 200)
        res = self.client.patch(
            '/api/django/marketing/parametres/',
            data={'plafond_envois_jour': 100},
            content_type='application/json', **auth)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['plafond_envois_jour'], 100)
