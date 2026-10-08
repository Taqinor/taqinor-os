"""APAR36 — fêtes mobiles unifiées sur les libellés canoniques de
``core.calendar`` (C-APAR-051) : après ``seed_ma_holidays`` 2026, les 4 fêtes
sont vues comme saisies par l'écran ET par les deux rappels ; une saisie à
l'écran ne double pas une ligne semée ; saisir un Aïd pose aussi son
« (2e jour) ». Les anciens libellés de l'écran restent lus (alias).
"""
import datetime

from django.test import TestCase

from apps.notifications.calendar_utils import rappel_fetes_mobiles
from apps.notifications.management.commands.seed_ma_holidays import (
    seed_holidays_for_company,
)
from apps.notifications.models import Holiday
from apps.notifications.tasks import _fetes_manquantes
from apps.parametres.fetes_mobiles import (
    FETES_MOBILES_LIBELLES, enregistrer_fetes_mobiles, fetes_mobiles_saisies,
)
from authentication.models import Company
from core.calendar import MOROCCAN_MOVABLE_HOLIDAYS

DEBUT_2026 = datetime.date(2026, 1, 1)


class FetesLibellesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR36', slug='apar36')

    def test_libelles_lus_dans_core_calendar(self):
        noms = set(MOROCCAN_MOVABLE_HOLIDAYS[2026].values())
        for libelle in FETES_MOBILES_LIBELLES.values():
            self.assertIn(libelle, noms)

    def test_seed_2026_vu_comme_saisi_partout(self):
        seed_holidays_for_company(self.company, annee=2026)
        saisies = fetes_mobiles_saisies(self.company, 2026)
        self.assertEqual(saisies, {
            'aid_el_fitr': '2026-03-20', 'aid_el_adha': '2026-05-27',
            '1er_moharram': '2026-06-17', 'aid_el_mawlid': '2026-08-26'})
        self.assertIsNone(rappel_fetes_mobiles(self.company, 2026))
        self.assertEqual(_fetes_manquantes(self.company, 2026), [])

    def test_saisie_ecran_sans_doublon_apres_seed(self):
        seed_holidays_for_company(self.company, annee=2026)
        enregistrer_fetes_mobiles(
            self.company, 2026, {'aid_el_fitr': '2026-03-20'},
            aujourd_hui=DEBUT_2026)
        self.assertEqual(Holiday.objects.filter(
            company=self.company, nom='Aïd al-Fitr').count(), 1)
        self.assertEqual(Holiday.objects.filter(
            company=self.company, nom='Aïd al-Fitr (2e jour)').count(), 1)

    def test_deuxieme_jour_pose_et_deplace(self):
        enregistrer_fetes_mobiles(self.company, 2027, {
            'aid_el_fitr': '2027-03-10', 'aid_el_adha': '2027-05-17',
            '1er_moharram': '2027-06-06', 'aid_el_mawlid': '2027-08-15',
        }, aujourd_hui=DEBUT_2026)
        deux = Holiday.objects.get(
            company=self.company, nom='Aïd al-Fitr (2e jour)')
        self.assertEqual(deux.date, datetime.date(2027, 3, 11))
        self.assertTrue(Holiday.objects.filter(
            company=self.company, nom='Aïd al-Adha (2e jour)',
            date=datetime.date(2027, 5, 18)).exists())
        self.assertFalse(Holiday.objects.filter(
            company=self.company, nom__startswith='Nouvel An hégirien (').exists())
        # Correction de la date : le 2e jour suit, sans seconde ligne.
        enregistrer_fetes_mobiles(
            self.company, 2027, {'aid_el_fitr': '2027-03-11'},
            aujourd_hui=DEBUT_2026)
        lignes = Holiday.objects.filter(
            company=self.company, nom='Aïd al-Fitr (2e jour)')
        self.assertEqual(list(lignes.values_list('date', flat=True)),
                         [datetime.date(2027, 3, 12)])

    def test_ancien_libelle_reste_lu(self):
        Holiday.objects.create(
            company=self.company, nom='Aïd el-Fitr',
            date=datetime.date(2027, 3, 10), recurrent_annuel=False)
        self.assertEqual(
            fetes_mobiles_saisies(self.company, 2027)['aid_el_fitr'],
            '2027-03-10')
