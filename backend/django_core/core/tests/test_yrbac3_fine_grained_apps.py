"""YRBAC3 — allow/deny par app sur le régime ``<app>_voir``/``<app>_gerer``.

Le régime YRBAC3 remplace un gatage grossier par ``IsResponsableOrAdmin`` (tout
porteur de rôle avec au moins une permission d'écriture ailleurs passait, y
compris en écriture, sans granularité) par une paire de codes
``<app>_voir``/``<app>_gerer`` lue par ``ScopedPermission`` (lecture ≠ écriture
par méthode HTTP), avec repli légacy préservé pour les comptes sans rôle fin.

SOLMVP (2026-09-21) — les 5 apps d'origine (qhse, gestion_projet, contrats,
litiges, kb) sont sorties du MVP solaire : les cas paramétrés sont RE-ANCRÉS sur
4 modules GARDÉS qui portent le même régime (calepinage, adsengine, visites,
sav). Voir le bloc de commentaire au-dessus des classes.

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


# ─────────────────────────────────────────────────────────────────────────────
# SOLMVP — RE-ANCRAGE des cas paramétrés sur des modules GARDÉS.
#
# Les 5 classes d'origine visaient qhse / gestion_projet / contrats / litiges /
# kb : ces apps sont sorties du MVP solaire (``core.parked`` /
# ``docs/parked-modules.md``), leurs urls ne sont plus montées, donc les 25
# tests ne mesuraient plus qu'un 404. La GARDE elle-même — « sans permission
# 403, ``_voir`` seul lit mais n'écrit pas, ``_gerer`` écrit, un compte légacy
# garde son accès historique » — est intacte : elle est simplement rebranchée
# sur les 4 modules CONSERVÉS qui portent exactement le même régime
# lecture ≠ écriture (``read_permission``/``write_permission`` lus par
# ``core.permissions.ScopedPermission``, ou la paire
# ``HasPermissionOrLegacy`` de ``apps/sav``), avec le même repli légacy
# (``_user_has_or_legacy`` / ``HasPermissionOrLegacy`` — même règle : rôle fin
# ⇒ code exigé, pas de rôle fin ⇒ comportement historique du palier
# Responsable). Les codes utilisés sont ceux du catalogue
# ``apps/roles/models.py``. Les 5 classes d'origine reviendront avec leurs
# modules (recette § 5 de ``docs/parked-modules.md``) ; leur forme exacte est
# dans l'historique git.
# ─────────────────────────────────────────────────────────────────────────────


class CalepinageAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "calepinage"
    list_path = "/api/django/calepinage/calepinages/"
    voir_code = "calepinage_voir"
    gerer_code = "calepinage_gerer"


class AdsengineAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "adsengine"
    list_path = "/api/django/adsengine/annotations/"
    voir_code = "adsengine_view"
    gerer_code = "adsengine_manage"


class VisitesAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "visites"
    list_path = "/api/django/visites/visites/"
    voir_code = "visites_voir"
    # ``VisiteTerrainViewSet`` exprime son code d'écriture PAR ACTION
    # (``PERMISSIONS_ECRITURE``) : la création exige ``visites_creer``.
    gerer_code = "visites_creer"


class SavAllowDenyTests(_FineGrainedAppAllowDenyMixin, TestCase):
    app_label = "sav"
    list_path = "/api/django/sav/tickets/"
    voir_code = "sav_voir"
    gerer_code = "sav_gerer"
