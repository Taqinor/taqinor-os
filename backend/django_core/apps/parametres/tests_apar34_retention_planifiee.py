"""APAR34 — la rétention d'audit « armée » s'applique sans commande manuelle
(C-APAR-048, D-APAR-3) : tâche Celery ``parametres.purger_audit`` au beat
quotidien, routée ``scheduled``, appelant l'UNIQUE purgeur au plancher 365 j.
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.parametres.models import CompanyProfile, SettingsAuditLog
from apps.parametres.retention import PURGE_FIELD, PURGE_SECTION
from apps.parametres.scheduled import purger_audit
from authentication.models import Company

TACHE = 'parametres.purger_audit'


def _age(model, obj, days):
    model.objects.filter(pk=obj.pk).update(
        timestamp=timezone.now() - timezone.timedelta(days=days))


class TacheAuBeatTests(SimpleTestCase):
    def test_planifiee_quotidienne_et_routee(self):
        from django.conf import settings

        from erp_agentique.celery import app

        entrees = [e for e in app.conf.beat_schedule.values()
                   if e['task'] == TACHE]
        self.assertEqual(len(entrees), 1)
        horaire = entrees[0]['schedule']
        # Quotidienne : tous les jours du mois / de la semaine, une heure fixe.
        self.assertEqual(len(horaire.hour), 1)
        self.assertEqual(len(horaire.day_of_month), 31)
        self.assertEqual(len(horaire.day_of_week), 7)
        self.assertEqual(settings.CELERY_TASK_ROUTES[TACHE]['queue'],
                         'scheduled')

    def test_enregistree_apres_autodecouverte(self):
        from erp_agentique.celery import app

        app.loader.import_default_modules()
        self.assertIn(TACHE, app.tasks)


class RetentionPlanifieeTests(TestCase):
    def setUp(self):
        self.armee = Company.objects.create(nom='Armée', slug='apar34-armee')
        CompanyProfile.objects.create(
            company=self.armee, audit_retention_days=400)
        self.illimitee = Company.objects.create(
            nom='Illimitée', slug='apar34-illimitee')
        CompanyProfile.objects.create(
            company=self.illimitee, audit_retention_days=0)
        self.lignes = {}
        for company in (self.armee, self.illimitee):
            vieille = AuditLog.objects.create(
                company=company, action=AuditLog.Action.LOGIN,
                object_repr='vieille')
            _age(AuditLog, vieille, 500)
            recente = AuditLog.objects.create(
                company=company, action=AuditLog.Action.LOGIN,
                object_repr='recente')
            _age(AuditLog, recente, 100)
            reglage = SettingsAuditLog.objects.create(
                company=company, section='profil', field='rib')
            _age(SettingsAuditLog, reglage, 500)
            self.lignes[company.pk] = (vieille, recente, reglage)

    def test_purge_sans_commande_manuelle(self):
        resultat = purger_audit()
        self.assertEqual(resultat['audit_deleted'], 1)
        self.assertEqual(resultat['settings_deleted'], 1)
        vieille, recente, reglage = self.lignes[self.armee.pk]
        self.assertFalse(AuditLog.objects.filter(pk=vieille.pk).exists())
        self.assertTrue(AuditLog.objects.filter(pk=recente.pk).exists())
        self.assertFalse(SettingsAuditLog.objects.filter(
            pk=reglage.pk).exists())
        self.assertEqual(SettingsAuditLog.objects.filter(
            company=self.armee, section=PURGE_SECTION,
            field=PURGE_FIELD).count(), 1)

    def test_societe_a_zero_intouchee(self):
        purger_audit()
        vieille, recente, reglage = self.lignes[self.illimitee.pk]
        self.assertTrue(AuditLog.objects.filter(pk=vieille.pk).exists())
        self.assertTrue(SettingsAuditLog.objects.filter(
            pk=reglage.pk).exists())
        self.assertFalse(SettingsAuditLog.objects.filter(
            company=self.illimitee, section=PURGE_SECTION).exists())

    def test_jamais_sous_le_plancher_legal(self):
        CompanyProfile.objects.filter(company=self.armee).update(
            audit_retention_days=30)
        purger_audit()
        _, recente, _ = self.lignes[self.armee.pk]
        # 100 j < 365 j de plancher : la ligne reste.
        self.assertTrue(AuditLog.objects.filter(pk=recente.pk).exists())
