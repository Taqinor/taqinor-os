"""ACHT74 (C-ACHT-070) — `date_prochaine_calibration` dérivée à chaque écriture
(vrais mois calendaires), filtre `?a_calibrer=1` aligné sur le badge,
`calibrer` refuse une date future ou antérieure à la dernière calibration.

Rejoue COUT-5 : `POST 201 prochaine None badge True`, filtre sans l'outil,
intervalle 1 -> 2027-10-08, `2023-03-01 -> 2024-02-29`, 2099 et 2020 acceptés.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.outillage.tests_acht74_calibration"
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.outillage.models import Outillage

User = get_user_model()
URL = '/api/django/outillage/outils/'


class CalibrationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT74', slug='acht74-co')
        self.user = User.objects.create_user(
            username='resp-acht74', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.jour = datetime.date.today()

    def _creer(self, **extra):
        corps = {'nom': 'Testeur', 'intervalle_calibration_mois': 12}
        corps.update(extra)
        r = self.api.post(URL, corps, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def test_creation_derive_la_prochaine_et_le_filtre(self):
        derniere = self.jour - datetime.timedelta(days=1100)
        data = self._creer(date_derniere_calibration=str(derniere))
        attendue = derniere.replace(year=derniere.year + 1) \
            if not (derniere.month == 2 and derniere.day == 29) \
            else datetime.date(derniere.year + 1, 2, 28)
        self.assertEqual(data['date_prochaine_calibration'], str(attendue))
        self.assertTrue(data['a_calibrer'])
        r = self.api.get(URL, {'a_calibrer': '1'})
        ids = [o['id'] for o in r.data['results']]
        self.assertIn(data['id'], ids)

    def test_jamais_calibre_dans_le_filtre(self):
        data = self._creer()
        self.assertTrue(data['a_calibrer'])
        r = self.api.get(URL, {'a_calibrer': '1'})
        self.assertIn(data['id'], [o['id'] for o in r.data['results']])

    def test_patch_et_calibrer_en_vrais_mois(self):
        data = self._creer()
        r = self.api.patch(f'{URL}{data["id"]}/', {
            'date_derniere_calibration': str(self.jour)}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['a_calibrer'])
        self.assertEqual(r.data['date_prochaine_calibration'],
                         str(self.jour.replace(year=self.jour.year + 1))
                         if not (self.jour.month == 2
                                 and self.jour.day == 29)
                         else str(datetime.date(self.jour.year + 1, 2, 28)))
        r = self.api.patch(f'{URL}{data["id"]}/', {
            'intervalle_calibration_mois': 1}, format='json')
        from dateutil.relativedelta import relativedelta
        self.assertEqual(r.data['date_prochaine_calibration'],
                         str(self.jour + relativedelta(months=1)))

    def test_calibrer_mars_2023(self):
        data = self._creer()
        r = self.api.post(f'{URL}{data["id"]}/calibrer/',
                          {'date_calibration': '2023-03-01'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['date_prochaine_calibration'], '2024-03-01')

    def test_calibrer_date_future_ou_anterieure_refusee(self):
        data = self._creer()
        r = self.api.post(f'{URL}{data["id"]}/calibrer/',
                          {'date_calibration': '2099-01-01'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('futur', str(r.data))
        self.api.post(f'{URL}{data["id"]}/calibrer/',
                      {'date_calibration': str(self.jour)}, format='json')
        r = self.api.post(f'{URL}{data["id"]}/calibrer/',
                          {'date_calibration': '2020-01-01'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('antérieure', str(r.data))
        outil = Outillage.objects.get(pk=data['id'])
        self.assertEqual(outil.date_derniere_calibration, self.jour)
