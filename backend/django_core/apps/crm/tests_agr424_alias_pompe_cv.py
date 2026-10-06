"""AGR424 — l'alias déprécié ``pompe_cv`` (AGR401) n'est plus servi.

Les lecteurs frontend ont migré vers ``pompe_actuelle_cv`` (AGR126, AGR415,
AGR420) : le détail d'un lead et d'un SiteProfile ne sert plus ``pompe_cv``.
La clé ``pompe_cv`` d'``etude_params`` (puissance RETENUE, sortie du moteur)
n'est pas concernée.

Run :
    python manage.py test apps.crm.tests_agr424_alias_pompe_cv -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, SiteProfile

User = get_user_model()


class AliasPompeCvRetire(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agr424-co', defaults={'nom': 'AGR424 Co'})
        self.user = User.objects.create_user(
            username='agr424_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_le_detail_du_lead_ne_sert_plus_l_alias(self):
        lead = Lead.objects.create(
            company=self.company, nom='Ferme', type_installation='agricole',
            pompe_actuelle_cv=Decimal('7.50'))
        resp = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['pompe_actuelle_cv'], '7.50')
        self.assertNotIn('pompe_cv', resp.data)

    def test_le_detail_du_site_profile_ne_sert_plus_l_alias(self):
        client = Client.objects.create(company=self.company, nom='Ferme SP')
        sp = SiteProfile.objects.create(
            company=self.company, client=client,
            type_installation='agricole', pompe_actuelle_cv=Decimal('5.50'))
        resp = self.api.get(f'/api/django/crm/site-profiles/{sp.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['pompe_actuelle_cv'], '5.50')
        self.assertNotIn('pompe_cv', resp.data)

    def test_un_patch_pompe_cv_reste_sans_effet(self):
        lead = Lead.objects.create(
            company=self.company, nom='Ferme 2', type_installation='agricole',
            pompe_actuelle_cv=Decimal('7.50'))
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/', {'pompe_cv': '12'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.pompe_actuelle_cv, Decimal('7.50'))
