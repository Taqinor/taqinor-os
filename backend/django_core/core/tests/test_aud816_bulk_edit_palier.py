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
appliquée émet ``core.events.bulk_edit_applied``.

La ligne ``AuditLog`` produite par cet événement est vérifiée dans
``apps/audit/tests_aud8_journal.py`` : ``core`` est une couche de FONDATION et
n'importe jamais ``apps.audit``, PAS MÊME depuis ses tests (contrat
import-linter ``core-foundation-is-a-base-layer``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.test import APIRequestFactory, force_authenticate

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

    # ── Émission de l'événement de traçabilité ────────────────────────────
    def test_lot_applique_emet_bulk_edit_applied(self):
        from core import events

        recus = []
        events.bulk_edit_applied.connect(
            lambda sender, **kw: recus.append(kw),
            dispatch_uid='aud816_test_spy')
        self.addCleanup(
            events.bulk_edit_applied.disconnect,
            dispatch_uid='aud816_test_spy')

        n = bulk_edit.apply_bulk_edit(
            'aud816.utilisateurs', self.company, self.responsable,
            [self.cible.pk], {'is_active': False})
        self.assertEqual(n, 1)
        self.assertEqual(len(recus), 1)
        recu = recus[0]
        self.assertEqual(recu['target'], 'aud816.utilisateurs')
        self.assertEqual(recu['fields'], ['is_active'])
        self.assertEqual(recu['count'], 1)
        self.assertEqual(recu['company'], self.company)
        self.assertEqual(recu['user'], self.responsable)

    def test_lot_vide_n_emet_rien(self):
        from core import events

        recus = []
        events.bulk_edit_applied.connect(
            lambda sender, **kw: recus.append(kw),
            dispatch_uid='aud816_test_spy_vide')
        self.addCleanup(
            events.bulk_edit_applied.disconnect,
            dispatch_uid='aud816_test_spy_vide')

        autre = Company.objects.create(nom='AUD816 Autre')
        n = bulk_edit.apply_bulk_edit(
            'aud816.utilisateurs', autre, self.responsable,
            [self.cible.pk], {'is_active': False})
        self.assertEqual(n, 0)
        self.assertEqual(recus, [])
