"""AUDV12 (DRAFT165-66/69) — planifie en tâches Celery récurrentes deux
relances GED documentées « à planifier en tâche périodique » mais jamais
câblées : `relancer_demandes_document_dues` (XGED8, relance UNITAIRE déjà
câblée côté écran, la version de masse n'avait aucune tâche) et
`notifier_planifications_echues` (XGED15, aucune tâche sœur ne l'appelait
malgré les tâches sœurs déjà planifiées — relances signataires/expiration/
intégrité archives). Couvre le multi-société (best-effort, une société KO
n'interrompt jamais les autres) et l'isolation des tenants suspendus (SCA19).
La joignabilité au beat (présence dans `erp_agentique.celery.app.conf.
beat_schedule` + routage `scheduled`) est vérifiée génériquement par
`core.tests.test_celery_task_routes`.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.ged.models import Cabinet, DemandeDocument, Document, Folder, PlanificationDocument
from apps.ged.tasks import (
    notifier_planifications_echues_task, relancer_demandes_document_dues_task,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class RelancerDemandesDocumentDuesTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co_a = make_company('audv12-relance-a', 'AUDV12 Relance A')
        cls.co_b = make_company('audv12-relance-b', 'AUDV12 Relance B')
        cls.admin_a = make_user(cls.co_a, 'audv12-relance-admin-a')
        cls.admin_b = make_user(cls.co_b, 'audv12-relance-admin-b')
        cab_a = Cabinet.objects.create(company=cls.co_a, nom='Admin')
        cab_b = Cabinet.objects.create(company=cls.co_b, nom='Admin')
        cls.folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cab_a, nom='Dossier A')
        cls.folder_b = Folder.objects.create(
            company=cls.co_b, cabinet=cab_b, nom='Dossier B')
        cls.demande_a = DemandeDocument.objects.create(
            company=cls.co_a, folder=cls.folder_a, libelle='CIN',
            utilisateur=cls.admin_a)
        cls.demande_b = DemandeDocument.objects.create(
            company=cls.co_b, folder=cls.folder_b, libelle='RIB',
            utilisateur=cls.admin_b)

    def test_relance_toutes_les_demandes_en_attente(self):
        result = relancer_demandes_document_dues_task()
        self.assertEqual(result['relances'], 2)
        self.demande_a.refresh_from_db()
        self.demande_b.refresh_from_db()
        self.assertEqual(self.demande_a.nombre_relances, 1)
        self.assertEqual(self.demande_b.nombre_relances, 1)

    def test_demande_soldee_non_relancee(self):
        from apps.ged.models import DEMANDE_DOC_SOLDEE
        self.demande_a.statut = DEMANDE_DOC_SOLDEE
        self.demande_a.save(update_fields=['statut'])
        result = relancer_demandes_document_dues_task()
        self.assertEqual(result['relances'], 1)
        self.demande_a.refresh_from_db()
        self.assertEqual(self.demande_a.nombre_relances, 0)

    def test_societe_suspendue_exclue(self):
        self.co_b.actif = False
        self.co_b.save(update_fields=['actif'])
        result = relancer_demandes_document_dues_task()
        self.assertEqual(result['relances'], 1)
        self.demande_b.refresh_from_db()
        self.assertEqual(self.demande_b.nombre_relances, 0)


class NotifierPlanificationsEcheesTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co_a = make_company('audv12-planif-a', 'AUDV12 Planif A')
        cls.co_b = make_company('audv12-planif-b', 'AUDV12 Planif B')
        cls.admin_a = make_user(cls.co_a, 'audv12-planif-admin-a')
        cls.admin_b = make_user(cls.co_b, 'audv12-planif-admin-b')
        cab_a = Cabinet.objects.create(company=cls.co_a, nom='Admin')
        cab_b = Cabinet.objects.create(company=cls.co_b, nom='Admin')
        folder_a = Folder.objects.create(
            company=cls.co_a, cabinet=cab_a, nom='Dossier A')
        folder_b = Folder.objects.create(
            company=cls.co_b, cabinet=cab_b, nom='Dossier B')
        doc_a = Document.objects.create(
            company=cls.co_a, folder=folder_a, nom='Contrat A')
        doc_b = Document.objects.create(
            company=cls.co_b, folder=folder_b, nom='Contrat B')
        cls.planif_a = PlanificationDocument.objects.create(
            company=cls.co_a, document=doc_a, libelle='Relancer J+7',
            echeance=date.today() - timedelta(days=1), assigne_a=cls.admin_a)
        cls.planif_b = PlanificationDocument.objects.create(
            company=cls.co_b, document=doc_b, libelle='Relancer J+7',
            echeance=date.today() - timedelta(days=1), assigne_a=cls.admin_b)

    def test_notifie_toutes_les_planifications_echues(self):
        result = notifier_planifications_echues_task()
        self.assertEqual(result['notifications'], 2)
        self.planif_a.refresh_from_db()
        self.planif_b.refresh_from_db()
        self.assertTrue(self.planif_a.notifiee)
        self.assertTrue(self.planif_b.notifiee)

    def test_planification_future_non_notifiee(self):
        self.planif_a.echeance = date.today() + timedelta(days=5)
        self.planif_a.save(update_fields=['echeance'])
        result = notifier_planifications_echues_task()
        self.assertEqual(result['notifications'], 1)
        self.planif_a.refresh_from_db()
        self.assertFalse(self.planif_a.notifiee)

    def test_societe_suspendue_exclue(self):
        self.co_b.actif = False
        self.co_b.save(update_fields=['actif'])
        result = notifier_planifications_echues_task()
        self.assertEqual(result['notifications'], 1)
        self.planif_b.refresh_from_db()
        self.assertFalse(self.planif_b.notifiee)

    def test_idempotent_rerun(self):
        notifier_planifications_echues_task()
        result = notifier_planifications_echues_task()
        self.assertEqual(result['notifications'], 0)
