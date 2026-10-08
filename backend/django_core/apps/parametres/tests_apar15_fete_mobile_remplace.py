"""APAR15 — corriger une fête mobile REMPLACE sa date (une seule ligne par
société + libellé + année) et journalise ancien → nouveau (C-APAR-050)."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.notifications.models import Holiday
from apps.parametres.fetes_mobiles import (
    enregistrer_fetes_mobiles,
    fetes_mobiles_saisies,
)
from apps.parametres.models import SettingsAuditLog
from authentication.models import Company

User = get_user_model()

AUJOURD_HUI = datetime.date(2026, 10, 8)
DATES_2027 = {
    'aid_el_fitr': '2027-03-10',
    'aid_el_adha': '2027-05-17',
    '1er_moharram': '2027-06-07',
    'aid_el_mawlid': '2027-08-16',
}


class FeteMobileRemplaceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR15 Co', slug='apar15-co')
        self.admin = User.objects.create_user(
            username='apar15_admin', password='x', role_legacy='admin',
            company=self.company)
        enregistrer_fetes_mobiles(
            self.company, 2027, DATES_2027, aujourd_hui=AUJOURD_HUI,
            user=self.admin)

    def _adha_2027(self):
        return list(Holiday.objects.filter(
            company=self.company, nom='Aïd el-Adha', date__year=2027,
        ).values_list('date', flat=True))

    def test_correction_laisse_une_seule_ligne(self):
        enregistrer_fetes_mobiles(
            self.company, 2027, {'aid_el_adha': '2027-05-18'},
            aujourd_hui=AUJOURD_HUI, user=self.admin)
        # Persistance : recompter par libellé et année.
        self.assertEqual(self._adha_2027(), [datetime.date(2027, 5, 18)])
        self.assertEqual(
            fetes_mobiles_saisies(self.company, 2027)['aid_el_adha'],
            '2027-05-18')

    def test_correction_journalisee_ancien_nouveau(self):
        enregistrer_fetes_mobiles(
            self.company, 2027, {'aid_el_adha': '2027-05-18'},
            aujourd_hui=AUJOURD_HUI, user=self.admin)
        ligne = SettingsAuditLog.objects.filter(
            company=self.company, section='fetes_mobiles',
            field='aid_el_adha', old_value='2027-05-17').get()
        self.assertEqual(ligne.new_value, '2027-05-18')
        self.assertEqual(ligne.user_id, self.admin.pk)

    def test_renvoi_identique_ne_journalise_rien(self):
        avant = SettingsAuditLog.objects.filter(
            company=self.company, section='fetes_mobiles').count()
        enregistrer_fetes_mobiles(
            self.company, 2027, DATES_2027, aujourd_hui=AUJOURD_HUI,
            user=self.admin)
        self.assertEqual(SettingsAuditLog.objects.filter(
            company=self.company, section='fetes_mobiles').count(), avant)

    def test_doublon_herite_resorbe(self):
        Holiday.objects.create(
            company=self.company, nom='Aïd el-Adha',
            date=datetime.date(2027, 5, 19), recurrent_annuel=False)
        enregistrer_fetes_mobiles(
            self.company, 2027, {'aid_el_adha': '2027-05-18'},
            aujourd_hui=AUJOURD_HUI, user=self.admin)
        self.assertEqual(self._adha_2027(), [datetime.date(2027, 5, 18)])

    def test_par_l_api_au_nom_de_l_admin(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        annee = datetime.date.today().year + 1
        dates = {k: v.replace('2027', str(annee)) for k, v in DATES_2027.items()}
        url = '/api/django/parametres/fetes-mobiles/enregistrer/'
        r = api.post(url, {'annee': annee, 'dates': dates}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = api.post(url, {'annee': annee, 'dates': {
            'aid_el_adha': f'{annee}-05-18'}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Holiday.objects.filter(
            company=self.company, nom='Aïd el-Adha', date__year=annee,
        ).count(), 1)
        self.assertTrue(SettingsAuditLog.objects.filter(
            company=self.company, section='fetes_mobiles',
            field='aid_el_adha', user=self.admin,
            new_value=f'{annee}-05-18').exists())
