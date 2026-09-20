"""NTOBS31 — job beat quotidien qui garantit les 2 ``KpiAlerte`` par défaut
(drill de restauration périmé > 35 j, quota saturé >= 100 %) pour chaque
société ACTIVE. Le calcul + l'évaluation restent dans
``apps.reporting.kpi_alertes`` (voir
``apps/reporting/tests_ntobs31_kpi_fiabilite.py``) — ce module teste
UNIQUEMENT le provisionnement idempotent, résolu ici via
``django.apps.apps.get_model`` (core reste une couche de fondation, aucun
import statique d'``apps.reporting``)."""
from decimal import Decimal

from django.apps import apps as django_apps
from django.test import TestCase

from authentication.models import Company
from core.tasks import assurer_alertes_fiabilite_kpi_task

KpiAlerte = django_apps.get_model('reporting', 'KpiAlerte')


class AssurerAlertesFiabiliteKpiTest(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(
            nom='NTOBS31 A', slug='ntobs31-alertes-a', actif=True)
        self.co_b = Company.objects.create(
            nom='NTOBS31 B', slug='ntobs31-alertes-b', actif=True)
        self.co_inactive = Company.objects.create(
            nom='NTOBS31 Inactive', slug='ntobs31-alertes-inactive',
            actif=False)

    def test_cree_les_2_alertes_par_defaut_par_societe_active(self):
        result = assurer_alertes_fiabilite_kpi_task()
        self.assertEqual(result['crees'], 4)
        for company in (self.co_a, self.co_b):
            self.assertTrue(KpiAlerte.objects.filter(
                company=company, kpi='jours_depuis_dernier_drill_reussi',
                operateur=KpiAlerte.Operateur.SUP,
                seuil=Decimal('35')).exists())
            self.assertTrue(KpiAlerte.objects.filter(
                company=company, kpi='quota_le_plus_charge_pct',
                operateur=KpiAlerte.Operateur.SUP_EGAL,
                seuil=Decimal('100')).exists())

    def test_societe_inactive_est_ignoree(self):
        assurer_alertes_fiabilite_kpi_task()
        self.assertFalse(KpiAlerte.objects.filter(
            company=self.co_inactive).exists())

    def test_idempotent_un_second_passage_ne_duplique_rien(self):
        assurer_alertes_fiabilite_kpi_task()
        total_apres_1er_passage = KpiAlerte.objects.count()

        second = assurer_alertes_fiabilite_kpi_task()

        self.assertEqual(second['crees'], 0)
        self.assertEqual(KpiAlerte.objects.count(), total_apres_1er_passage)

    def test_ne_touche_pas_une_alerte_personnalisee_sur_le_meme_kpi(self):
        """Un seuil DIFFÉRENT du défaut est une alerte distincte : le job
        ajoute le garde-fou par défaut À CÔTÉ, sans y toucher."""
        personnalisee = KpiAlerte.objects.create(
            company=self.co_a, nom='Mon seuil perso',
            kpi='jours_depuis_dernier_drill_reussi',
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('50'),
            destinataire_role='responsable')

        assurer_alertes_fiabilite_kpi_task()

        personnalisee.refresh_from_db()
        self.assertEqual(personnalisee.seuil, Decimal('50'))
        self.assertEqual(personnalisee.destinataire_role, 'responsable')
        self.assertEqual(KpiAlerte.objects.filter(
            company=self.co_a,
            kpi='jours_depuis_dernier_drill_reussi').count(), 2)

    def test_ne_duplique_pas_une_alerte_deja_identique_au_defaut(self):
        """Une alerte déjà créée à la main avec EXACTEMENT le triplet par
        défaut (société+KPI+opérateur+seuil) n'est pas dupliquée, et ses
        autres champs (ici ``nom``) ne sont pas écrasés."""
        existante = KpiAlerte.objects.create(
            company=self.co_a, nom='Déjà configurée par un admin',
            kpi='quota_le_plus_charge_pct',
            operateur=KpiAlerte.Operateur.SUP_EGAL, seuil=Decimal('100'),
            destinataire_role='responsable')

        result = assurer_alertes_fiabilite_kpi_task()

        self.assertEqual(KpiAlerte.objects.filter(
            company=self.co_a, kpi='quota_le_plus_charge_pct').count(), 1)
        existante.refresh_from_db()
        self.assertEqual(existante.nom, 'Déjà configurée par un admin')
        self.assertEqual(existante.destinataire_role, 'responsable')
        # 3 créées (drill A, drill B, quota B) — le quota A existait déjà.
        self.assertEqual(result['crees'], 3)
