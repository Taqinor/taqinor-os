"""AUD813 / AUD816 — la moitié « trace au Journal d'activité » des deux
correctifs de fondation, testée DEPUIS le satellite ``audit``.

Pourquoi ici et pas dans ``core/tests/`` : ``core`` est une couche de FONDATION
et n'a pas le droit d'importer ``apps.audit``, pas même depuis ses tests
(contrat import-linter ``core-foundation-is-a-base-layer``). C'est donc le
satellite qui vérifie sa propre trace — exactement comme il possède déjà
``receivers.py`` pour les événements de ``core.events``.

Couvre :
  * AUD813 — ``('core', 'ChangelogEntry')`` est dans ``TRACKED_MODELS`` et une
    publication écrit une ligne ``AuditLog`` ;
  * AUD816 — ``core.events.bulk_edit_applied`` (émis par ``core.bulk_edit``,
    qui écrit par ``queryset.update()`` donc SANS aucun signal CRUD) produit
    UNE ligne ``AuditLog`` portant la cible, les champs, le nombre de lignes,
    l'auteur et la société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import bulk_edit
from core.views import ChangelogViewSet

from . import recorder
from .models import AuditLog
from .signals import TRACKED_MODELS

User = get_user_model()


class Aud813ChangelogJournalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD813 Journal SARL')
        cls.editeur = User.objects.create_superuser(
            username='aud813j_editeur', password='x',
            email='aud813j@example.com')
        cls.editeur.company = cls.company
        cls.editeur.save(update_fields=['company'])
        cls.factory = APIRequestFactory()

    def test_changelog_entry_est_suivi(self):
        self.assertIn(('core', 'ChangelogEntry'), TRACKED_MODELS)

    def test_publication_ecrit_une_ligne_auditlog(self):
        req = self.factory.post(
            '/changelog/', {'titre': 'Tracée AUD813', 'publie': True},
            format='json')
        force_authenticate(req, user=self.editeur)
        # Le recorder ne journalise QUE pendant une requête : on simule
        # ``AuditActorMiddleware`` autour de l'appel de la vue.
        recorder.begin_request(req)
        try:
            resp = ChangelogViewSet.as_view({'post': 'create'})(req)
        finally:
            recorder.end_request()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            AuditLog.objects.filter(
                object_repr__icontains='Tracée AUD813',
                action=AuditLog.Action.CREATE).exists())


def _users_target(company, user):
    return User.objects.filter(company=company)


class Aud816BulkEditJournalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD816 Journal SARL')
        cls.responsable = User.objects.create_user(
            username='aud816j_resp', password='x', company=cls.company,
            role_legacy='responsable')
        cls.cible = User.objects.create_user(
            username='aud816j_cible', password='x', company=cls.company,
            is_active=True)

    def setUp(self):
        bulk_edit.register_bulk_target(
            'aud816j.utilisateurs', 'Utilisateurs', ['is_active'],
            _users_target)

    def test_lot_applique_produit_une_ligne_de_journal(self):
        avant = AuditLog.objects.count()
        n = bulk_edit.apply_bulk_edit(
            'aud816j.utilisateurs', self.company, self.responsable,
            [self.cible.pk], {'is_active': False})
        self.assertEqual(n, 1)
        self.assertEqual(AuditLog.objects.count(), avant + 1)
        ligne = AuditLog.objects.order_by('-id').first()
        self.assertEqual(ligne.action, AuditLog.Action.UPDATE)
        self.assertEqual(ligne.company, self.company)
        self.assertEqual(ligne.user, self.responsable)
        self.assertIn('aud816j.utilisateurs', ligne.detail)
        self.assertIn('is_active', ligne.detail)
        self.assertIn('1 ligne', ligne.detail)

    def test_lot_vide_ne_journalise_rien(self):
        avant = AuditLog.objects.count()
        autre = Company.objects.create(nom='AUD816 Journal Autre')
        n = bulk_edit.apply_bulk_edit(
            'aud816j.utilisateurs', autre, self.responsable,
            [self.cible.pk], {'is_active': False})
        self.assertEqual(n, 0)
        self.assertEqual(AuditLog.objects.count(), avant)
