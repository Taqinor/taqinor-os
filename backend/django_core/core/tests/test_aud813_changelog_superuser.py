"""AUD813 — le changelog produit est GLOBAL (aucune FK société) et republié
sur un endpoint public sans authentification : son écriture ne peut donc pas
rester ouverte à l'administrateur de N'IMPORTE QUEL tenant.

Constat d'origine : ``ChangelogViewSet.get_permissions`` rendait ``IsAdminRole``
hors lecture, or ``is_admin_role`` est vrai pour ``role_legacy='admin'`` de
n'importe quelle société — l'admin du tenant « Client B » pouvait POST une note
publiée visible chez TOUS les tenants (et sur ``/publicapi/changelog/`` en
AllowAny), ou DELETE les notes de l'éditeur.

Après correctif : toute méthode non sûre est réservée au superutilisateur
Django (le même palier ``_IsSuperUser`` que ``TenantUsageSnapshotViewSet`` /
``OutboxEventViewSet`` / ``maintenance_toggle``), la lecture reste ouverte à
tout utilisateur authentifié, et ``('core', 'ChangelogEntry')`` est suivi par
le Journal d'activité (``TRACKED_MODELS``).

La moitié « trace au Journal » est vérifiée dans
``apps/audit/tests_aud8_journal.py`` : ``core`` est une couche de FONDATION et
n'a pas le droit d'importer ``apps.audit``, PAS MÊME depuis ses tests (contrat
import-linter ``core-foundation-is-a-base-layer``) — c'est le satellite qui
teste sa propre trace.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core.models import ChangelogEntry
from core.views import ChangelogViewSet

User = get_user_model()


class Aud813ChangelogEcritureSuperuserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Client B')
        # Admin de tenant : role_legacy='admin' + is_staff — exactement le
        # profil qui obtenait 200 sur POST/PATCH/DELETE avant AUD813.
        cls.tenant_admin = User.objects.create_user(
            username='aud813_admin_tenant', password='x',
            role_legacy='admin', company=cls.company, is_staff=True)
        cls.editeur = User.objects.create_superuser(
            username='aud813_editeur', password='x',
            email='aud813@example.com')
        cls.editeur.company = cls.company
        cls.editeur.save(update_fields=['company'])
        cls.note = ChangelogEntry.objects.create(
            titre='Note éditeur', publie=True)
        cls.factory = APIRequestFactory()

    # ── Écriture refusée à l'admin de tenant ──────────────────────────────
    def test_post_refuse_a_l_admin_de_tenant(self):
        req = self.factory.post(
            '/changelog/', {'titre': 'Injectée', 'publie': True},
            format='json')
        force_authenticate(req, user=self.tenant_admin)
        resp = ChangelogViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            ChangelogEntry.objects.filter(titre='Injectée').exists())

    def test_patch_refuse_a_l_admin_de_tenant(self):
        req = self.factory.patch(
            f'/changelog/{self.note.pk}/', {'titre': 'Détournée'},
            format='json')
        force_authenticate(req, user=self.tenant_admin)
        resp = ChangelogViewSet.as_view(
            {'patch': 'partial_update'})(req, pk=self.note.pk)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.note.refresh_from_db()
        self.assertEqual(self.note.titre, 'Note éditeur')

    def test_delete_refuse_a_l_admin_de_tenant(self):
        req = self.factory.delete(f'/changelog/{self.note.pk}/')
        force_authenticate(req, user=self.tenant_admin)
        resp = ChangelogViewSet.as_view(
            {'delete': 'destroy'})(req, pk=self.note.pk)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            ChangelogEntry.objects.filter(pk=self.note.pk).exists())

    # ── La lecture reste ouverte ──────────────────────────────────────────
    def test_lecture_reste_200_pour_l_admin_de_tenant(self):
        req = self.factory.get('/changelog/')
        force_authenticate(req, user=self.tenant_admin)
        resp = ChangelogViewSet.as_view({'get': 'list'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── Le superutilisateur (éditeur) garde l'écriture ────────────────────
    def test_superuser_publie_toujours(self):
        req = self.factory.post(
            '/changelog/', {'titre': 'Note produit', 'publie': True},
            format='json')
        force_authenticate(req, user=self.editeur)
        resp = ChangelogViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    # La trace au Journal (TRACKED_MODELS + ligne AuditLog) est vérifiée dans
    # apps/audit/tests_aud8_journal.py — voir la docstring du module.
