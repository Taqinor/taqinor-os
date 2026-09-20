"""NTOBS31 — 3 KPI « Fiabilité » cross-module dans le catalogue fermé
``KpiAlerte.Kpi`` : ``uptime_moyen_12_mois``, ``jours_depuis_dernier_drill_
reussi``, ``quota_le_plus_charge_pct``. Aucun nouveau moteur de KPI : les
trois délèguent à des sources DÉJÀ BÂTIES par le groupe NTOBS
(``core.sla.SlaSnapshot``, ``core.models.BackupRun``,
``core.usage_limits.usage_summary``).

Critère de la tâche : les 3 KPI se calculent (par société), sont
sélectionnables dans le catalogue générique existant (picker KpiAlerte —
« sélecteur de KPI du Dashboard générique », aucun écran dédié séparé), et
une ``KpiAlerte`` se déclenche sur le cas « drill périmé » (> 35 jours)."""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core.models import BackupRun
from core.sla import SlaSnapshot, premier_du_mois

from .kpi_alertes import _KPI_COMPUTERS, evaluate_kpi_alerte, kpis_disponibles
from .models import KpiAlerte

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', role_legacy='responsable',
        company=company)


class CatalogueTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs31-cat', 'NTOBS31 Catalogue')

    def test_les_trois_valeurs_sont_au_catalogue(self):
        for valeur in (
                'uptime_moyen_12_mois', 'jours_depuis_dernier_drill_reussi',
                'quota_le_plus_charge_pct'):
            self.assertIn(valeur, KpiAlerte.Kpi.values)

    def test_les_trois_sont_proposees_dans_le_picker(self):
        proposables = kpis_disponibles(self.company)
        for valeur in (
                'uptime_moyen_12_mois', 'jours_depuis_dernier_drill_reussi',
                'quota_le_plus_charge_pct'):
            self.assertIn(valeur, proposables)

    def test_les_trois_ont_un_calculateur_branche(self):
        for kpi in (
                KpiAlerte.Kpi.UPTIME_MOYEN_12_MOIS,
                KpiAlerte.Kpi.JOURS_DEPUIS_DERNIER_DRILL_REUSSI,
                KpiAlerte.Kpi.QUOTA_LE_PLUS_CHARGE_PCT):
            self.assertIn(kpi, _KPI_COMPUTERS)

    def test_valeurs_tiennent_dans_max_length(self):
        champ = KpiAlerte._meta.get_field('kpi')
        for valeur in (
                'uptime_moyen_12_mois', 'jours_depuis_dernier_drill_reussi',
                'quota_le_plus_charge_pct'):
            self.assertLessEqual(len(valeur), champ.max_length)

    def test_alerte_creable_sur_chacun_des_trois(self):
        for kpi in (
                KpiAlerte.Kpi.UPTIME_MOYEN_12_MOIS,
                KpiAlerte.Kpi.JOURS_DEPUIS_DERNIER_DRILL_REUSSI,
                KpiAlerte.Kpi.QUOTA_LE_PLUS_CHARGE_PCT):
            alerte = KpiAlerte.objects.create(
                company=self.company, kpi=kpi,
                operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('35'))
            alerte.full_clean()
            self.assertEqual(alerte.kpi, kpi.value)


class UptimeMoyen12MoisTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs31-up-a', 'NTOBS31 Uptime A')
        self.autre = make_company('ntobs31-up-b', 'NTOBS31 Uptime B')
        self.calc = _KPI_COMPUTERS[KpiAlerte.Kpi.UPTIME_MOYEN_12_MOIS]

    def _snap(self, company, mois_avant, uptime):
        periode = premier_du_mois()
        annee = periode.year
        mois = periode.month - mois_avant
        while mois <= 0:
            mois += 12
            annee -= 1
        return SlaSnapshot.objects.create(
            company=company, periode=periode.replace(year=annee, month=mois),
            uptime_pct=Decimal(str(uptime)))

    def test_none_sans_snapshot(self):
        self.assertIsNone(self.calc(self.company, None))

    def test_moyenne_des_snapshots_des_12_derniers_mois(self):
        self._snap(self.company, 1, '99.0')
        self._snap(self.company, 2, '97.0')
        self.assertEqual(self.calc(self.company, None), Decimal('98.0'))

    def test_scope_a_la_societe(self):
        self._snap(self.autre, 1, '50.0')
        self.assertIsNone(self.calc(self.company, None))

    def test_snapshot_trop_ancien_exclu(self):
        self._snap(self.company, 13, '10.0')
        self.assertIsNone(self.calc(self.company, None))


class JoursDepuisDernierDrillReussiTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs31-drill', 'NTOBS31 Drill')
        self.calc = _KPI_COMPUTERS[
            KpiAlerte.Kpi.JOURS_DEPUIS_DERNIER_DRILL_REUSSI]

    def test_none_sans_drill(self):
        self.assertIsNone(self.calc(self.company, None))

    def test_jours_depuis_le_dernier_drill_reussi(self):
        BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_TERMINE, company=None,
            termine_le=timezone.now() - datetime.timedelta(days=40))
        self.assertEqual(self.calc(self.company, None), Decimal(40))

    def test_prend_le_plus_recent(self):
        BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_TERMINE, company=None,
            termine_le=timezone.now() - datetime.timedelta(days=40))
        BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_TERMINE, company=None,
            termine_le=timezone.now() - datetime.timedelta(days=5))
        self.assertEqual(self.calc(self.company, None), Decimal(5))

    def test_drill_echoue_ignore(self):
        BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_ECHEC, company=None,
            termine_le=timezone.now() - datetime.timedelta(days=1))
        self.assertIsNone(self.calc(self.company, None))

    def test_drill_purge_ignore(self):
        BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_TERMINE, company=None,
            termine_le=timezone.now() - datetime.timedelta(days=1),
            purge_is_deleted=True)
        self.assertIsNone(self.calc(self.company, None))

    def test_sauvegarde_export_non_drill_ignoree(self):
        BackupRun.objects.create(
            kind=BackupRun.KIND_EXPORT, statut=BackupRun.STATUT_TERMINE,
            company=self.company,
            termine_le=timezone.now() - datetime.timedelta(days=1))
        self.assertIsNone(self.calc(self.company, None))


class QuotaLePlusChargePctTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs31-quota', 'NTOBS31 Quota')
        self.calc = _KPI_COMPUTERS[KpiAlerte.Kpi.QUOTA_LE_PLUS_CHARGE_PCT]

    def test_prend_le_ratio_le_plus_charge(self):
        resume = {'ressources': [
            {'nom': 'Stockage GED', 'utilise': 40, 'limite': 100, 'unite': 'Go'},
            {'nom': 'Appels API', 'utilise': 950, 'limite': 1000, 'unite': 'appels'},
        ]}
        with mock.patch(
                'core.usage_limits.usage_summary', return_value=resume):
            self.assertEqual(self.calc(self.company, None), Decimal('95.0'))

    def test_ignore_les_ressources_illimitees(self):
        resume = {'ressources': [
            {'nom': 'Import CSV', 'utilise': 10, 'limite': None, 'unite': ''},
        ]}
        with mock.patch(
                'core.usage_limits.usage_summary', return_value=resume):
            self.assertIsNone(self.calc(self.company, None))

    def test_none_sans_ressource(self):
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value={'ressources': []}):
            self.assertIsNone(self.calc(self.company, None))


class DrillPerimeAlerteTests(TestCase):
    """Done= « une KpiAlerte se déclenche sur le cas drill périmé en test »."""

    def setUp(self):
        self.company = make_company('ntobs31-alerte', 'NTOBS31 Alerte')
        self.user = make_user(self.company, 'ntobs31_alerte_u')

    def test_drill_de_plus_de_35_jours_declenche_lalerte(self):
        BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_TERMINE, company=None,
            termine_le=timezone.now() - datetime.timedelta(days=40))
        alerte = KpiAlerte.objects.create(
            company=self.company,
            kpi=KpiAlerte.Kpi.JOURS_DEPUIS_DERNIER_DRILL_REUSSI,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('35'))
        alerte.destinataires_utilisateurs.add(self.user)

        with mock.patch('apps.notifications.services.notify') as mock_notify:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte)

        self.assertEqual(valeur, Decimal(40))
        self.assertTrue(franchi)
        self.assertTrue(notifie)
        mock_notify.assert_called_once()

    def test_drill_recent_ne_declenche_rien(self):
        BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_TERMINE, company=None,
            termine_le=timezone.now() - datetime.timedelta(days=2))
        alerte = KpiAlerte.objects.create(
            company=self.company,
            kpi=KpiAlerte.Kpi.JOURS_DEPUIS_DERNIER_DRILL_REUSSI,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('35'))
        alerte.destinataires_utilisateurs.add(self.user)

        with mock.patch('apps.notifications.services.notify') as mock_notify:
            _valeur, franchi, notifie = evaluate_kpi_alerte(alerte)

        self.assertFalse(franchi)
        self.assertFalse(notifie)
        mock_notify.assert_not_called()

    def test_quota_sature_declenche_lalerte(self):
        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.QUOTA_LE_PLUS_CHARGE_PCT,
            operateur=KpiAlerte.Operateur.SUP_EGAL, seuil=Decimal('100'))
        alerte.destinataires_utilisateurs.add(self.user)

        with mock.patch(
                'apps.reporting.kpi_alertes._compute_quota_le_plus_charge_pct',
                return_value=Decimal('100.0')), \
            mock.patch(
                'apps.notifications.services.notify') as mock_notify:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte)

        self.assertEqual(valeur, Decimal('100.0'))
        self.assertTrue(franchi)
        self.assertTrue(notifie)
        mock_notify.assert_called_once()
