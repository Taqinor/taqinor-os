"""Tests FG389 — édition en masse généralisée (bulk edit).

Couvre :
  * registre de cibles + liste blanche de champs (champ hors liste rejeté) ;
  * application : seules les lignes du queryset scopé sont modifiées
    (id hors société ignoré) ;
  * endpoint : palier responsable/admin exigé (AUD816), cible inconnue → 404,
    champ non modifiable → 400 ;
  * découplage : cible enregistrée sur un modèle de FONDATION (CustomUser).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import bulk_edit
from core.views import BulkEditViewSet

User = get_user_model()


def _users_target(company, user):
    return User.objects.filter(company=company)


class BulkEditEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.u1 = User.objects.create_user(
            username='a', password='x', company=cls.company, is_active=True)
        cls.u2 = User.objects.create_user(
            username='b', password='x', company=cls.company, is_active=True)
        cls.foreign = User.objects.create_user(
            username='c', password='x', company=cls.other, is_active=True)

    def setUp(self):
        bulk_edit.register_bulk_target(
            'utilisateurs', 'Utilisateurs', ['is_active'], _users_target)

    def test_apply_scoped_only(self):
        ids = [self.u1.pk, self.u2.pk, self.foreign.pk]
        n = bulk_edit.apply_bulk_edit(
            'utilisateurs', self.company, self.u1, ids, {'is_active': False})
        self.assertEqual(n, 2)  # foreign (autre société) ignoré
        self.foreign.refresh_from_db()
        self.assertTrue(self.foreign.is_active)  # inchangé

    def test_field_not_whitelisted_rejected(self):
        with self.assertRaises(bulk_edit.ChampNonModifiable):
            bulk_edit.apply_bulk_edit(
                'utilisateurs', self.company, self.u1, [self.u1.pk],
                {'is_superuser': True})

    def test_unknown_target_raises(self):
        with self.assertRaises(bulk_edit.CibleInconnue):
            bulk_edit.apply_bulk_edit('nope', self.company, self.u1, [1], {})


class BulkEditViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        # AUD816 — l'édition en masse exige désormais le palier
        # responsable/admin (un compte sans rôle obtenait 200 auparavant).
        cls.user = User.objects.create_user(
            username='u1', password='x', company=cls.company,
            role_legacy='admin')
        cls.factory = APIRequestFactory()

    def setUp(self):
        bulk_edit.register_bulk_target(
            'utilisateurs', 'Utilisateurs', ['is_active'], _users_target)

    def _apply(self, body):
        req = self.factory.post('/bulk-edit/appliquer/', body, format='json')
        force_authenticate(req, user=self.user)
        return BulkEditViewSet.as_view({'post': 'appliquer'})(req)

    def test_unknown_target_404(self):
        resp = self._apply({'target': 'nope', 'ids': [1]})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_field_not_modifiable_400(self):
        resp = self._apply({'target': 'utilisateurs', 'ids': [self.user.pk],
                            'changes': {'is_superuser': True}})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_ok(self):
        resp = self._apply({'target': 'utilisateurs', 'ids': [self.user.pk],
                            'changes': {'is_active': False}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['modifies'], 1)


class NTUX31EditionMasseFinePermissionTests(TestCase):
    """NTUX31 — `ux.edition_masse.executer` s'ajoute EN PLUS du palier
    responsable/admin (AUD816) sur le repli PAR DÉFAUT de `appliquer/`, sans
    jamais retirer l'accès d'un compte SANS rôle fin (voir `BulkEditViewSetTests`,
    inchangé — `role_legacy='admin'`)."""

    @classmethod
    def setUpTestData(cls):
        from apps.roles.models import Role

        cls.company = Company.objects.create(nom='ACME NTUX31')
        cls.role_sans_code = Role.objects.create(
            company=cls.company, nom='Responsable maison', est_systeme=False,
            permissions=['users_voir', 'crm_voir'],
        )
        cls.role_avec_code = Role.objects.create(
            company=cls.company, nom='Responsable outillé', est_systeme=False,
            permissions=['users_voir', 'crm_voir', 'ux_edition_masse_executer'],
        )
        cls.user_sans_code = User.objects.create_user(
            username='ntux31-sans', password='x', company=cls.company,
            role=cls.role_sans_code)
        cls.user_avec_code = User.objects.create_user(
            username='ntux31-avec', password='x', company=cls.company,
            role=cls.role_avec_code)
        cls.factory = APIRequestFactory()

    def setUp(self):
        bulk_edit.register_bulk_target(
            'utilisateurs', 'Utilisateurs', ['is_active'], _users_target)

    def _apply(self, user, body):
        req = self.factory.post('/bulk-edit/appliquer/', body, format='json')
        force_authenticate(req, user=user)
        return BulkEditViewSet.as_view({'post': 'appliquer'})(req)

    def test_refuse_sans_le_code_fin(self):
        resp = self._apply(self.user_sans_code, {
            'target': 'utilisateurs', 'ids': [self.user_sans_code.pk],
            'changes': {'is_active': False},
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_autorise_avec_le_code_fin(self):
        resp = self._apply(self.user_avec_code, {
            'target': 'utilisateurs', 'ids': [self.user_avec_code.pk],
            'changes': {'is_active': False},
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
