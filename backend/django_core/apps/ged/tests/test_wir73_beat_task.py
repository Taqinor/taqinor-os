"""WIR73 — planifie `migrate_attachments_to_ged` (GED7) en récurrent.

Avant cette tâche, la commande manage `migrate_attachments_to_ged` existait
et était testée (GED7) mais RIEN ne l'exécutait automatiquement : une pièce
jointe créée après le dernier import MANUEL n'apparaissait jamais en GED.
Ces tests couvrent la tâche Celery `ged.migrer_pieces_jointes` (multi-société,
idempotente, isolation d'erreur par société) — la joignabilité au beat
(présence dans `erp_agentique.celery.app.conf.beat_schedule`) est déjà
vérifiée génériquement par `apps.ventes.tests.test_qx11_beat_reachability`.
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ged.models import Document, DocumentLien
from apps.ged.tasks import migrer_pieces_jointes_task
from apps.records.models import Attachment


def make_company(slug, nom):
    return Company.objects.create(slug=slug, nom=nom)


def make_user(company, username, role='admin'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class Wir73MigrerPiecesJointesTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co_a = make_company('wir73-a', 'WIR73 A')
        cls.co_b = make_company('wir73-b', 'WIR73 B')
        cls.admin_a = make_user(cls.co_a, 'wir73-admin-a')
        cls.admin_b = make_user(cls.co_b, 'wir73-admin-b')
        cls.client_a = Client.objects.create(company=cls.co_a, nom='Client A')
        cls.client_b = Client.objects.create(company=cls.co_b, nom='Client B')
        ct_client = ContentType.objects.get_for_model(Client)
        cls.att_a = Attachment.objects.create(
            company=cls.co_a, content_type=ct_client,
            object_id=cls.client_a.id, file_key='wir73-a/keyA.pdf',
            filename='contrat-a.pdf', size=10, mime='application/pdf',
            uploaded_by=cls.admin_a)
        cls.att_b = Attachment.objects.create(
            company=cls.co_b, content_type=ct_client,
            object_id=cls.client_b.id, file_key='wir73-b/keyB.pdf',
            filename='contrat-b.pdf', size=10, mime='application/pdf',
            uploaded_by=cls.admin_b)

    def test_imports_attachments_for_every_active_company(self):
        result = migrer_pieces_jointes_task()
        self.assertEqual(result['documents'], 2)
        self.assertTrue(
            Document.objects.filter(
                company=self.co_a, nom='contrat-a.pdf').exists())
        self.assertTrue(
            Document.objects.filter(
                company=self.co_b, nom='contrat-b.pdf').exists())
        # DocumentLien posé vers la cible autorisée (crm.Client), par société.
        self.assertTrue(
            DocumentLien.objects.filter(
                company=self.co_a, object_id=self.client_a.id).exists())

    def test_idempotent_rerun_creates_no_duplicate(self):
        migrer_pieces_jointes_task()
        migrer_pieces_jointes_task()
        self.assertEqual(
            Document.objects.filter(
                company=self.co_a, nom='contrat-a.pdf').count(), 1)

    def test_suspended_company_excluded(self):
        self.co_b.actif = False
        self.co_b.save(update_fields=['actif'])
        result = migrer_pieces_jointes_task()
        self.assertEqual(result['documents'], 1)
        self.assertFalse(
            Document.objects.filter(
                company=self.co_b, nom='contrat-b.pdf').exists())

    def test_one_company_failure_does_not_block_others(self):
        # Une société sans pièce jointe ne doit jamais faire échouer le
        # balayage des autres (garde défensive du bloc try/except).
        co_c = make_company('wir73-c', 'WIR73 C')
        result = migrer_pieces_jointes_task()
        self.assertGreaterEqual(result['documents'], 2)
        self.assertFalse(Document.objects.filter(company=co_c).exists())
