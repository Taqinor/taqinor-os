"""AUD816 — ``/core/bulk-edit/appliquer/`` était ouvert à TOUT utilisateur
authentifié et écrivait par ``queryset.update()``.

Constat d'origine : ``BulkEditViewSet.permission_classes = [IsAuthenticated]``
sans palier de rôle, et ``core.bulk_edit.apply_bulk_edit`` fait
``qs.update(**changes)`` — donc aucun ``Model.save()``, aucun ``full_clean()``,
aucun signal : pas de ligne au Journal d'activité, pas d'``updated_at``. Les
cibles d'aujourd'hui sont étroites (3 cibles CPQ, aucun champ de prix) mais
CHAQUE cible future héritait du défaut du socle.

Après correctif : palier responsable/admin par défaut (une cible peut déclarer
sa propre garde via ``register_bulk_target(permission=…)``) et une opération
appliquée émet ``core.events.bulk_edit_applied`` → UNE ligne ``AuditLog``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.audit.models import AuditLog
from authentication.models import Company
from core import bulk_edit
from core.views import BulkEditViewSet

User = get_user_model()


def _users_target(company, user):
    return User.objects.filter(company=company)


class _JamaisAutorise(BasePermission):
    """Garde propre à une cible, plus stricte que le palier du socle."""

    def has_permission(self, request, view):
        return False


class Aud816BulkEditPalierTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD816 SARL')
        cls.viewer = User.objects.create_user(
            username='aud816_viewer', password='x', company=cls.company,
            role_legacy='normal')
        cls.responsable = User.objects.create_user(
            username='aud816_resp', password='x', company=cls.company,
            role_legacy='responsable')
        cls.cible = User.objects.create_user(
            username='aud816_cible', password='x', company=cls.company,
            is_active=True)
        cls.factory = APIRequestFactory()

    def setUp(self):
        bulk_edit.register_bulk_target(
            'aud816.utilisateurs', 'Utilisateurs', ['is_active'],
            _users_target)

    def _apply(self, acteur, body):
        req = self.factory.post('/bulk-edit/appliquer/', body, format='json')
        force_authenticate(req, user=acteur)
        return BulkEditViewSet.as_view({'post': 'appliquer'})(req)

    # ── Palier de rôle ────────────────────────────────────────────────────
    def test_viewer_ne_peut_plus_appliquer(self):
        resp = self._apply(self.viewer, {
            'target': 'aud816.utilisateurs', 'ids': [self.cible.pk],
            'changes': {'is_active': False}})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.cible.refresh_from_db()
        self.assertTrue(self.cible.is_active)

    def test_responsable_applique_toujours(self):
        resp = self._apply(self.responsable, {
            'target': 'aud816.utilisateurs', 'ids': [self.cible.pk],
            'changes': {'is_active': False}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['modifies'], 1)

    def test_catalogue_reste_ouvert_en_lecture(self):
        req = self.factory.get('/bulk-edit/targets/')
        force_authenticate(req, user=self.viewer)
        resp = BulkEditViewSet.as_view({'get': 'targets'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── Garde déclarée PAR LA CIBLE ───────────────────────────────────────
    def test_permission_declaree_par_la_cible_prime(self):
        bulk_edit.register_bulk_target(
            'aud816.verrouillee', 'Verrouillée', ['is_active'],
            _users_target, permission=_JamaisAutorise)
        resp = self._apply(self.responsable, {
            'target': 'aud816.verrouillee', 'ids': [self.cible.pk],
            'changes': {'is_active': False}})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Traçabilité ───────────────────────────────────────────────────────
    def test_lot_applique_produit_une_ligne_de_journal(self):
        avant = AuditLog.objects.count()
        n = bulk_edit.apply_bulk_edit(
            'aud816.utilisateurs', self.company, self.responsable,
            [self.cible.pk], {'is_active': False})
        self.assertEqual(n, 1)
        self.assertEqual(AuditLog.objects.count(), avant + 1)
        ligne = AuditLog.objects.order_by('-id').first()
        self.assertEqual(ligne.action, AuditLog.Action.UPDATE)
        self.assertEqual(ligne.company, self.company)
        self.assertEqual(ligne.user, self.responsable)
        self.assertIn('aud816.utilisateurs', ligne.detail)
        self.assertIn('is_active', ligne.detail)
        self.assertIn('1 ligne', ligne.detail)

    def test_lot_vide_ne_journalise_rien(self):
        avant = AuditLog.objects.count()
        autre = Company.objects.create(nom='AUD816 Autre')
        n = bulk_edit.apply_bulk_edit(
            'aud816.utilisateurs', autre, self.responsable,
            [self.cible.pk], {'is_active': False})
        self.assertEqual(n, 0)
        self.assertEqual(AuditLog.objects.count(), avant)
