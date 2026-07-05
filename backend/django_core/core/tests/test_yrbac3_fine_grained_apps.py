"""YRBAC3 — allow/deny par app pour qhse/gestion_projet/contrats/litiges/kb.

Ces 5 apps étaient gatées SEULEMENT par ``IsResponsableOrAdmin`` (tout porteur
de rôle avec au moins une permission d'écriture ailleurs passait, y compris en
écriture, sans granularité). YRBAC3 introduit ``<app>_voir``/``<app>_gerer`` +
``WriteScopedPermissionMixin`` (lecture ≠ écriture par méthode HTTP), avec repli
légacy préservé pour les comptes sans rôle fin.

Ce test prouve, par app, sur l'endpoint « liste » (GET) :

* un rôle ne portant AUCUNE des deux permissions → 403 en lecture ;
* un rôle portant SEULEMENT ``<app>_voir`` → 200 en lecture, 403 en écriture
  (POST) ;
* un rôle portant ``<app>_voir`` + ``<app>_gerer`` → 200 en lecture ET en
  écriture (le POST peut échouer en 400 de validation métier — jamais en 403) ;
* un compte LÉGACY sans rôle fin (``role_legacy=ROLE_RESPONSABLE``) garde
  l'accès historique complet (lecture ET écriture) — aucune régression.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

User = get_user_model()


def _client_for(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


class _FineGrainedAppAllowDenyMixin:
    """Exerce allow/deny GET+POST sur ``self.list_path`` pour une app YRBAC3.

    Sous-classes déclarent : ``app_label`` (préfixe de test unique),
    ``list_path`` (endpoint liste), ``voir_code``/``gerer_code``.
    """
    app_label = None
    list_path = None
    voir_code = None
    gerer_code = None

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug=f"yrbac3-{cls.app_label}",
            defaults={"nom": f"YRBAC3 {cls.app_label}"},
        )[0]

    def _user(self, suffix, perms=None, role_legacy=None):
        role = None
        if perms is not None:
            role = Role.objects.create(
                company=self.company,
                nom=f"{self.app_label}-{suffix}",
                permissions=perms,
            )
        kwargs = {}
        if role_legacy is not None:
            kwargs["role_legacy"] = role_legacy
        return User.objects.create_user(
            username=f"yrbac3-{self.app_label}-{suffix}",
            password="x",
            role=role,
            company=self.company,
            **kwargs,
        )

    def test_sans_permission_refuse_lecture(self):
        user = self._user("sans-perm", perms=[])
        resp = _client_for(user).get(self.list_path)
        self.assertEqual(resp.status_code, 403)

    def test_voir_seul_autorise_lecture(self):
        user = self._user("voir-seul", perms=[self.voir_code])
        resp = _client_for(user).get(self.list_path)
        self.assertEqual(resp.status_code, 200)

    def test_voir_seul_refuse_ecriture(self):
        user = self._user("voir-seul-post", perms=[self.voir_code])
        resp = _client_for(user).post(self.list_path, {}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_gerer_autorise_lecture_et_ecriture(self):
        user = self._user(
            "gerer", perms=[self.voir_code, self.gerer_code])
        client = _client_for(user)
        self.assertEqual(client.get(self.list_path).status_code, 200)
        resp = client.post(self.list_path, {}, format="json")
        # Jamais 403 (a la permission) — 2xx (créé) ou 400 (validation
        # métier, champs requis manquants dans ce POST minimal).
        self.assertNotEqual(resp.status_code, 403)

    def test_compte_legacy_garde_acces_historique(self):
        """Compte SANS rôle fin (role_legacy=Responsable) : accès complet
        préservé (repli HasPermissionOrLegacy / ScopedPermission)."""
        from authentication.models import CustomUser
        user = self._user(
            "legacy", perms=None, role_legacy=CustomUser.ROLE_RESPONSABLE)
        client = _client_for(user)
        self.assertEqual(client.get(self.list_path).status_code, 200)
        resp = client.post(self.list_path, {}, format="json")
        self.assertNotEqual(resp.status_code, 403)


class QhseAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "qhse"
    list_path = "/api/django/qhse/non-conformites/"
    voir_code = "qhse_voir"
    gerer_code = "qhse_gerer"


class GestionProjetAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "gestion_projet"
    list_path = "/api/django/gestion-projet/projets/"
    voir_code = "projet_voir"
    gerer_code = "projet_gerer"


class ContratsAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "contrats"
    list_path = "/api/django/contrats/contrats/"
    voir_code = "contrat_voir"
    gerer_code = "contrat_gerer"


class LitigesAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "litiges"
    list_path = "/api/django/litiges/reclamations/"
    voir_code = "litige_voir"
    gerer_code = "litige_gerer"


class KbAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "kb"
    list_path = "/api/django/kb/articles/"
    voir_code = "kb_voir"
    gerer_code = "kb_gerer"
