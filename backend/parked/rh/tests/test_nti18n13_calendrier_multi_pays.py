"""Tests NTI18N13 — généraliser la table de fériés FIXES de ``rh.holidays``

à plusieurs pays (MA/FR/SN/CI), sans changer le comportement par défaut.

Périmètre couvert ICI (moitié RH, pur Python, aucune base de données) : le
paramètre optionnel ``pays`` de ``is_ferie_fixe``/``is_jour_ouvre``/
``working_days``. Le câblage bout-en-bout (``Holiday.pays`` côté
``apps.notifications``, ``CompanyProfile.pays`` côté ``apps.parametres``,
sélection automatique du pays d'une société) est HORS PÉRIMÈTRE de ce module
et n'est pas testé ici — voir le rapport de la tâche.
"""
from datetime import date

from django.test import SimpleTestCase

from apps.rh import holidays


class ComportementMarocInchangeTests(SimpleTestCase):
    """Non-régression : sans ``pays``, tout appelant existant est inchangé."""

    def test_jours_feries_ma_toujours_reconnus(self):
        self.assertTrue(holidays.is_ferie_fixe(date(2026, 5, 1)))
        self.assertTrue(holidays.is_ferie_fixe(date(2026, 7, 30)))

    def test_working_days_defaut_identique_a_avant(self):
        # 2026-05-01 (Fête du Travail MA) tombe un vendredi : exclu.
        n = holidays.working_days(date(2026, 5, 1), date(2026, 5, 8))
        self.assertEqual(n, 5)

    def test_alias_retrocompatible_jours_feries_fixes_ma(self):
        self.assertIs(
            holidays.JOURS_FERIES_FIXES_MA,
            holidays.JOURS_FERIES_FIXES_PAR_PAYS['MA'])


class CalendrierMultiPaysTests(SimpleTestCase):
    def test_ferie_france_reconnu_avec_pays_fr(self):
        # 14 juillet 2026 (mardi) : fête nationale française.
        self.assertTrue(
            holidays.is_ferie_fixe(date(2026, 7, 14), pays='FR'))
        # Le même jour n'est PAS un férié marocain.
        self.assertFalse(
            holidays.is_ferie_fixe(date(2026, 7, 14), pays='MA'))

    def test_working_days_france_exclut_son_propre_ferie(self):
        # Semaine du lundi 2026-07-13 au vendredi 2026-07-17 : le 14/07
        # (mardi) est férié en France → 4 jours ouvrés au lieu de 5.
        n_fr = holidays.working_days(
            date(2026, 7, 13), date(2026, 7, 17), pays='FR')
        n_ma = holidays.working_days(
            date(2026, 7, 13), date(2026, 7, 17), pays='MA')
        self.assertEqual(n_fr, 4)
        self.assertEqual(n_ma, 5)

    def test_senegal_fete_independance(self):
        self.assertTrue(
            holidays.is_ferie_fixe(date(2026, 4, 4), pays='SN'))

    def test_cote_ivoire_fete_independance(self):
        self.assertTrue(
            holidays.is_ferie_fixe(date(2026, 8, 7), pays='CI'))

    def test_pays_inconnu_replie_sur_maroc(self):
        # Un code pays absent de la table ne casse jamais l'appel : repli MA.
        self.assertTrue(
            holidays.is_ferie_fixe(date(2026, 5, 1), pays='ZZ'))
        self.assertEqual(
            holidays.working_days(date(2026, 5, 1), date(2026, 5, 8), pays='ZZ'),
            holidays.working_days(date(2026, 5, 1), date(2026, 5, 8), pays='MA'))

    def test_extra_holidays_toujours_pris_en_compte_avec_pays(self):
        # Un férié société (mobile, ex. Aïd) reste exclu même avec pays='FR'.
        extra = [date(2026, 7, 16)]  # jeudi
        n = holidays.working_days(
            date(2026, 7, 13), date(2026, 7, 17), extra_holidays=extra,
            pays='FR')
        # 14/07 (férié FR) + 16/07 (extra) exclus → 3 jours ouvrés.
        self.assertEqual(n, 3)
