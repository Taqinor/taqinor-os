"""HOLIDAY-PAYS (complément NTI18N13) — ``Holiday.pays`` + filtrage
``calendar_utils.feries_entre`` + 3 nouveaux seeders (FR/SN/CI).

Couverture :
  - ``Holiday.pays`` défaut ``'MA'`` (additif, zéro régression pour le
    calendrier marocain existant) ;
  - ``feries_entre(..., pays=None)`` (défaut, comportement historique)
    ignore le pays et renvoie tout, ``pays='FR'``/``'MA'`` filtre ;
  - les 3 seeders (même forme EXACTE que ``seed_ma_holidays``) : idempotents,
    uniquement des fériés légaux FIXES, tagués avec le bon ``pays`` ;
  - les 3 commandes sont enregistrées dans le registre Django (déverrouille
    mécaniquement ``apps.parametres.onboarding_pays.seeder_disponible`` pour
    FR/SN/CI — NTI18N31, autre lane, aucun fichier de ce module n'y touche).
"""
import datetime

from django.core.management import call_command, get_commands
from django.test import TestCase

from authentication.models import Company

from .calendar_utils import feries_entre
from .models import Holiday
from .selectors import holidays_for_export, upsert_holiday


def _co(nom):
    return Company.objects.create(nom=nom, slug=nom.lower().replace(' ', '-'))


class HolidayPaysFieldTests(TestCase):
    def test_defaut_ma_zero_regression(self):
        co = _co('HolPaysCo1')
        h = Holiday.objects.create(
            company=co, date=datetime.date(2024, 1, 1),
            nom="Jour de l'An", recurrent_annuel=True)
        self.assertEqual(h.pays, 'MA')

    def test_pays_explicite(self):
        co = _co('HolPaysCo2')
        h = Holiday.objects.create(
            company=co, date=datetime.date(2024, 7, 14),
            nom='Fête Nationale', recurrent_annuel=True, pays='FR')
        self.assertEqual(h.pays, 'FR')


class FeriesEntreFiltragePaysTests(TestCase):
    def setUp(self):
        self.co = _co('HolPaysFiltre')
        Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 1, 1),
            nom="Jour de l'An MA", recurrent_annuel=True, pays='MA')
        Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 7, 14),
            nom='Fête Nationale FR', recurrent_annuel=True, pays='FR')

    def test_sans_pays_renvoie_tout_comportement_historique(self):
        # ZÉRO RÉGRESSION : un appelant qui ne passe jamais `pays` doit
        # continuer à voir TOUS les fériés de la société, quel que soit leur
        # pays.
        dates = feries_entre(
            self.co, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
        self.assertEqual(len(dates), 2)

    def test_filtre_par_pays_ma(self):
        dates = feries_entre(
            self.co, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31),
            pays='MA')
        self.assertEqual(dates, [datetime.date(2024, 1, 1)])

    def test_filtre_par_pays_fr(self):
        dates = feries_entre(
            self.co, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31),
            pays='FR')
        self.assertEqual(dates, [datetime.date(2024, 7, 14)])

    def test_pays_sans_aucune_correspondance_renvoie_vide(self):
        dates = feries_entre(
            self.co, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31),
            pays='SN')
        self.assertEqual(dates, [])


class HolidaysForExportSelectorTests(TestCase):
    """NTI18N45 — sélecteur cross-app en LECTURE pour
    ``apps.dataimport.holidays_import``."""

    def test_renvoie_les_champs_attendus_tries_pays_puis_date(self):
        co = _co('HolExportCo')
        Holiday.objects.create(
            company=co, date=datetime.date(2026, 12, 25), nom='Noël',
            pays='FR')
        Holiday.objects.create(
            company=co, date=datetime.date(2026, 1, 1),
            nom='Jour de l\'An', pays='FR', recurrent_annuel=True)
        lignes = holidays_for_export(co)
        self.assertEqual(len(lignes), 2)
        self.assertEqual(
            [ligne['date'] for ligne in lignes],
            [datetime.date(2026, 1, 1), datetime.date(2026, 12, 25)])
        self.assertEqual(set(lignes[0]), {'pays', 'date', 'nom',
                                          'recurrent_annuel'})

    def test_isolation_societe(self):
        co1 = _co('HolExportIso1')
        co2 = _co('HolExportIso2')
        Holiday.objects.create(
            company=co2, date=datetime.date(2026, 1, 1), nom='Fuite')
        self.assertEqual(holidays_for_export(co1), [])

    def test_sans_societe_renvoie_liste_vide(self):
        self.assertEqual(holidays_for_export(None), [])


class UpsertHolidaySelectorTests(TestCase):
    """NTI18N45 — écriture cross-app IDEMPOTENTE par (company, pays, date)
    pour ``apps.dataimport.holidays_import``."""

    def test_premier_appel_cree(self):
        co = _co('HolUpsertCo1')
        holiday, cree = upsert_holiday(
            co, pays='FR', date=datetime.date(2026, 7, 14),
            nom='Fête nationale', recurrent_annuel=True)
        self.assertTrue(cree)
        self.assertEqual(holiday.nom, 'Fête nationale')

    def test_rejouer_avec_meme_cle_met_a_jour_sans_dupliquer(self):
        co = _co('HolUpsertCo2')
        upsert_holiday(
            co, pays='FR', date=datetime.date(2026, 7, 14),
            nom='Ancien libellé')
        _holiday, cree = upsert_holiday(
            co, pays='FR', date=datetime.date(2026, 7, 14),
            nom='Nouveau libellé')
        self.assertFalse(cree)
        self.assertEqual(
            Holiday.objects.filter(
                company=co, pays='FR', date=datetime.date(2026, 7, 14)
            ).count(), 1)
        self.assertEqual(
            Holiday.objects.get(
                company=co, pays='FR', date=datetime.date(2026, 7, 14)).nom,
            'Nouveau libellé')

    def test_deux_pays_meme_date_libelle_distinct_coexistent(self):
        co = _co('HolUpsertCo3')
        upsert_holiday(
            co, pays='FR', date=datetime.date(2026, 1, 1), nom='FR NY')
        upsert_holiday(
            co, pays='SN', date=datetime.date(2026, 1, 1), nom='SN NY')
        self.assertEqual(
            Holiday.objects.filter(
                company=co, date=datetime.date(2026, 1, 1)).count(), 2)


class SeedersFrSnCiRegistreTests(TestCase):
    """Les 3 commandes existent et sont visibles du registre Django — c'est
    exactement ce que lit `apps.parametres.onboarding_pays.seeder_disponible`
    (aucun import direct de ce module ici, juste la même vérification par le
    registre — frontière cross-app respectée)."""

    def test_les_trois_commandes_sont_enregistrees(self):
        commandes = get_commands()
        for nom in ('seed_holidays_fr', 'seed_holidays_sn', 'seed_holidays_ci'):
            with self.subTest(commande=nom):
                self.assertIn(nom, commandes)


class SeedHolidaysFrTests(TestCase):
    def test_seed_cree_8_feries_fixes_tagues_fr(self):
        from apps.notifications.management.commands.seed_holidays_fr import (
            FR_FIXED_HOLIDAYS,
        )
        co = _co('SeedFrCo')
        call_command('seed_holidays_fr', company_id=co.id)
        qs = Holiday.objects.filter(company=co)
        self.assertEqual(qs.count(), len(FR_FIXED_HOLIDAYS))
        self.assertEqual(qs.filter(pays='FR').count(), len(FR_FIXED_HOLIDAYS))
        self.assertEqual(qs.filter(recurrent_annuel=False).count(), 0)

    def test_seed_est_idempotent(self):
        co = _co('SeedFrCo2')
        call_command('seed_holidays_fr', company_id=co.id)
        call_command('seed_holidays_fr', company_id=co.id)
        from apps.notifications.management.commands.seed_holidays_fr import (
            FR_FIXED_HOLIDAYS,
        )
        self.assertEqual(
            Holiday.objects.filter(company=co).count(), len(FR_FIXED_HOLIDAYS))

    def test_scope_a_une_seule_societe(self):
        co1 = _co('SeedFrCo3')
        co2 = _co('SeedFrCo4')
        call_command('seed_holidays_fr', company_id=co1.id)
        self.assertEqual(Holiday.objects.filter(company=co2).count(), 0)


class SeedHolidaysSnTests(TestCase):
    def test_seed_cree_les_feries_fixes_tagues_sn(self):
        from apps.notifications.management.commands.seed_holidays_sn import (
            SN_FIXED_HOLIDAYS,
        )
        co = _co('SeedSnCo')
        call_command('seed_holidays_sn', company_id=co.id)
        qs = Holiday.objects.filter(company=co)
        self.assertEqual(qs.count(), len(SN_FIXED_HOLIDAYS))
        self.assertEqual(qs.filter(pays='SN').count(), len(SN_FIXED_HOLIDAYS))
        self.assertEqual(qs.filter(recurrent_annuel=False).count(), 0)

    def test_seed_est_idempotent(self):
        co = _co('SeedSnCo2')
        call_command('seed_holidays_sn', company_id=co.id)
        call_command('seed_holidays_sn', company_id=co.id)
        from apps.notifications.management.commands.seed_holidays_sn import (
            SN_FIXED_HOLIDAYS,
        )
        self.assertEqual(
            Holiday.objects.filter(company=co).count(), len(SN_FIXED_HOLIDAYS))


class SeedHolidaysCiTests(TestCase):
    def test_seed_cree_les_feries_fixes_tagues_ci(self):
        from apps.notifications.management.commands.seed_holidays_ci import (
            CI_FIXED_HOLIDAYS,
        )
        co = _co('SeedCiCo')
        call_command('seed_holidays_ci', company_id=co.id)
        qs = Holiday.objects.filter(company=co)
        self.assertEqual(qs.count(), len(CI_FIXED_HOLIDAYS))
        self.assertEqual(qs.filter(pays='CI').count(), len(CI_FIXED_HOLIDAYS))
        self.assertEqual(qs.filter(recurrent_annuel=False).count(), 0)

    def test_seed_est_idempotent(self):
        co = _co('SeedCiCo2')
        call_command('seed_holidays_ci', company_id=co.id)
        call_command('seed_holidays_ci', company_id=co.id)
        from apps.notifications.management.commands.seed_holidays_ci import (
            CI_FIXED_HOLIDAYS,
        )
        self.assertEqual(
            Holiday.objects.filter(company=co).count(), len(CI_FIXED_HOLIDAYS))
