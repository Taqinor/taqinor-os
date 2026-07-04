"""XGED15 — Chatter documentaire (notes, @mentions, activités planifiées).

Couvre :
  * `('ged', 'document')` est bien dans `ALLOWED_TARGETS` (chatter FG7 réutilisé) ;
  * une note @mention sur un document notifie l'utilisateur cité ;
  * le journal automatique des événements majeurs (nouvelle version, statut,
    partage, signature) ;
  * une activité planifiée échue notifie son assigné ;
  * la timeline mêle logs auto et notes.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import Cabinet, Document, DocumentActivity, Folder
from apps.records.models import ALLOWED_TARGETS

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XGed15Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged15-a', 'Xged15 A')
        self.admin_a = make_user(self.co_a, 'xged15-admin-a', 'admin')
        self.mentioned = make_user(self.co_a, 'xged15-mentioned', 'commercial')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat')


class AllowedTargetsTests(TestCase):
    def test_ged_document_is_allowed_target(self):
        self.assertIn(('ged', 'document'), ALLOWED_TARGETS)


class MentionTests(XGed15Base):
    def test_mention_notifies_user(self):
        from apps.notifications.models import Notification
        api = auth(self.admin_a)
        resp = api.post('/api/django/records/comments/', {
            'model': 'ged.document', 'id': self.doc.pk,
            'body': f'Merci de vérifier @{self.mentioned.username}',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            Notification.objects.filter(recipient=self.mentioned).exists())


class JournalAutomatiqueTests(XGed15Base):
    def test_nouvelle_version_journalisee(self):
        services.add_version(
            self.doc, file_key='k', company=self.co_a, filename='v1.pdf',
            uploaded_by=self.admin_a)
        self.assertTrue(
            DocumentActivity.objects.filter(
                document=self.doc, type_evenement='nouvelle_version').exists())

    def test_changement_statut_journalise(self):
        from apps.ged.models import LIFECYCLE_REVUE
        services.change_lifecycle_status(
            self.doc, LIFECYCLE_REVUE, user=self.admin_a)
        self.assertTrue(
            DocumentActivity.objects.filter(
                document=self.doc, type_evenement='changement_statut').exists())

    def test_partage_cree_journalise(self):
        services.create_partage(
            document=self.doc, company=self.co_a, created_by=self.admin_a)
        self.assertTrue(
            DocumentActivity.objects.filter(
                document=self.doc, type_evenement='partage_cree').exists())


class PlanificationTests(XGed15Base):
    def test_planifier_et_endpoint(self):
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc.pk}/planifier/', {
                'libelle': 'Relancer le client',
                'echeance': '2026-07-10',
                'assigne_a': self.admin_a.pk,
            })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_notifier_planifications_echues(self):
        from datetime import date
        from apps.notifications.models import Notification
        planif = services.planifier_document(
            self.doc, libelle='Relance', echeance=date(2020, 1, 1),
            assigne_a=self.admin_a, created_by=self.admin_a)
        notifiees = services.notifier_planifications_echues(
            self.co_a, today=date(2026, 1, 1))
        self.assertEqual(len(notifiees), 1)
        planif.refresh_from_db()
        self.assertTrue(planif.notifiee)
        self.assertTrue(
            Notification.objects.filter(recipient=self.admin_a).exists())

    def test_notifier_ignores_non_echues(self):
        from datetime import date
        services.planifier_document(
            self.doc, libelle='Future', echeance=date(2099, 1, 1),
            assigne_a=self.admin_a)
        notifiees = services.notifier_planifications_echues(
            self.co_a, today=date(2026, 1, 1))
        self.assertEqual(notifiees, [])


class TimelineTests(XGed15Base):
    def test_timeline_mixes_logs_and_notes(self):
        services.journaliser_evenement(
            self.doc, type_evenement='test_event', message='Test',
            utilisateur=self.admin_a)
        entries = selectors.timeline_document(self.doc)
        self.assertTrue(any(e['type'] == 'activite' for e in entries))

    def test_timeline_endpoint(self):
        services.journaliser_evenement(
            self.doc, type_evenement='test_event', utilisateur=self.admin_a)
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc.pk}/timeline/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) >= 1)
