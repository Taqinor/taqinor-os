"""YRBAC5 — WriteScopedPermissionMixin : lecture ≠ écriture par méthode HTTP.

Exerce le mixin sur un viewset SYNTHÉTIQUE (pas de dépendance à une app métier)
via un APIRequestFactory : un rôle `*_voir` seul lit (GET) mais est refusé en
écriture (POST/PATCH/DELETE) ; un rôle `*_gerer` écrit ; un compte légacy sans
rôle fin garde son accès historique.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import viewsets
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from apps.roles.models import Role
from core.permissions import WriteScopedPermissionMixin

User = get_user_model()


class _DummyViewSet(WriteScopedPermissionMixin, viewsets.ViewSet):
    read_permission = "stock_voir"
    write_permission = "stock_gerer"

    def list(self, request):
        from rest_framework.response import Response
        return Response([])

    def create(self, request):
        from rest_framework.response import Response
        return Response({}, status=201)


class WriteScopedMixinTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug="yrbac5", defaults={"nom": "YRBAC5"})[0]
        cls.factory = APIRequestFactory()

    def _user(self, username, perms):
        role = Role.objects.create(
            company=self.company, nom=f"role-{username}", permissions=perms)
        return User.objects.create_user(
            username=username, password="x", role=role, company=self.company)

    def _call(self, user, method):
        view = _DummyViewSet.as_view(
            {"get": "list", "post": "create"})
        req = getattr(self.factory, method)("/dummy/")
        force_authenticate(req, user=user)
        return view(req)

    def test_voir_seul_lit_mais_refuse_ecriture(self):
        user = self._user("voir-only", ["stock_voir"])
        self.assertEqual(self._call(user, "get").status_code, 200)
        self.assertEqual(self._call(user, "post").status_code, 403)

    def test_gerer_ecrit(self):
        user = self._user("gerer", ["stock_voir", "stock_gerer"])
        self.assertEqual(self._call(user, "get").status_code, 200)
        self.assertEqual(self._call(user, "post").status_code, 201)

    def test_sans_permission_refuse_lecture(self):
        user = self._user("aucune", ["crm_voir"])
        self.assertEqual(self._call(user, "get").status_code, 403)

    def test_anonyme_refuse(self):
        view = _DummyViewSet.as_view({"get": "list"})
        req = self.factory.get("/dummy/")
        # 401 (et non 403) : le seul authentificateur configuré
        # (CookieJWTAuthentication) expose un ``authenticate_header`` non nul,
        # donc DRF lève NotAuthenticated (401) pour une requête anonyme — c'est
        # la réponse correcte sous cette config d'auth ; le mixin est correct.
        self.assertEqual(view(req).status_code, 401)

    def test_none_read_permission_autorise_authentifie(self):
        """read_permission=None → tout authentifié lit (préserve l'historique)."""
        class _OpenRead(_DummyViewSet):
            read_permission = None
        user = self._user("open", ["crm_voir"])
        view = _OpenRead.as_view({"get": "list"})
        req = self.factory.get("/dummy/")
        force_authenticate(req, user=user)
        self.assertEqual(view(req).status_code, 200)
