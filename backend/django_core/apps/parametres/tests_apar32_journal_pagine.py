"""APAR32 — journal d'audit des réglages consultable sur toute la rétention
(C-APAR-043) : `count` = total réel, `offset` respecté, filtres champ/dates,
400 (pas 500) sur un `user`/`limit` invalide.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models import SettingsAuditLog
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()
URL = '/api/django/parametres/audit/'


class JournalPagineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR32', slug='apar32')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.user = User.objects.create_user(
            username='apar32', password='x', role=role, company=self.company)
        maintenant = timezone.now()
        for i in range(138):
            ligne = SettingsAuditLog.objects.create(
                company=self.company, user=self.user, section='profil',
                field='rib' if i % 2 else 'nom', field_label='Champ',
                old_value=str(i), new_value=str(i + 1))
            # Ligne n°1 = la plus récente (i=137), ligne n°138 = la plus vieille.
            SettingsAuditLog.objects.filter(pk=ligne.pk).update(
                timestamp=maintenant - datetime.timedelta(days=137 - i))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))

    def test_count_total_et_seconde_page(self):
        p1 = self.api.get(URL, {'limit': 50})
        self.assertEqual(p1.status_code, 200)
        self.assertEqual(p1.data['count'], 138)
        self.assertEqual(len(p1.data['results']), 50)
        self.assertEqual(p1.data['next'], 50)
        p2 = self.api.get(URL, {'limit': 50, 'offset': 50})
        self.assertEqual(p2.data['count'], 138)
        # La ligne n°51 (offset 50) : i = 137 - 50 = 87.
        self.assertEqual(p2.data['results'][0]['old_value'], '87')
        ids1 = {r['id'] for r in p1.data['results']}
        self.assertFalse(ids1 & {r['id'] for r in p2.data['results']})
        p3 = self.api.get(URL, {'limit': 50, 'offset': 100})
        self.assertEqual(len(p3.data['results']), 38)
        self.assertIsNone(p3.data['next'])

    def test_filtres_champ_et_dates(self):
        r = self.api.get(URL, {'field': 'rib', 'limit': 500})
        self.assertEqual(r.data['count'], 69)
        aujourd_hui = timezone.localdate()
        r = self.api.get(URL, {
            'date_debut': (aujourd_hui - datetime.timedelta(days=9)).isoformat(),
            'limit': 500})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(9 <= r.data['count'] <= 11, r.data['count'])

    def test_parametres_invalides_400(self):
        for params in ({'user': 'abc'}, {'limit': 'x'}, {'offset': '-1'},
                       {'limit': '0'}, {'date_debut': '2026-13-45'}):
            r = self.api.get(URL, params)
            self.assertEqual(r.status_code, 400, (params, r.data))
