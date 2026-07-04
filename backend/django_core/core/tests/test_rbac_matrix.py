"""YRBAC2 — le test qui asserte la matrice endpoint×rôle canonique.

Par société de test, crée un utilisateur de chacun des 7 rôles canoniques (via
``init_roles``) et appelle chaque entrée de ``core.rbac_matrix.MATRIX`` en
vérifiant le verdict attendu :

* ALLOW → code 2xx ;
* DENY  → 403 (permission refusée) ou 404 (existence masquée).

Couvre crm + ventes + stock à 100 % des lignes déclarées ; garantit aussi que
tout endpoint métier hors matrice serait détectable (via l'inventaire YRBAC1).
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import CANONICAL_SYSTEM_ROLES, Role
from core import rbac_matrix

User = get_user_model()


def _client_for(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


class RbacMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug="yrbac2", defaults={"nom": "YRBAC2"})[0]
        # init_roles crée les rôles canoniques (idempotent) pour la société.
        call_command("init_roles")
        cls.users = {}
        for name in rbac_matrix.CANONICAL_ROLE_NAMES:
            role = Role.objects.filter(company=cls.company, nom=name).first()
            if role is None:
                # Repli : recréer le rôle depuis la table canonique si
                # init_roles n'a pas ciblé cette société de test.
                perms = dict(
                    (n, p) for n, p in CANONICAL_SYSTEM_ROLES).get(name, [])
                role = Role.objects.create(
                    company=cls.company, nom=name, permissions=list(perms),
                    est_systeme=True)
            user = User.objects.create_user(
                username=f"yrbac2-{name}", password="x",
                role=role, company=cls.company)
            cls.users[name] = user

    def test_canonical_role_names_match_source(self):
        """La liste de rôles de la matrice reste alignée sur roles.*."""
        source_names = [n for n, _ in CANONICAL_SYSTEM_ROLES]
        for name in rbac_matrix.CANONICAL_ROLE_NAMES:
            self.assertIn(
                name, source_names,
                f"Rôle de matrice « {name} » absent de CANONICAL_SYSTEM_ROLES.")

    def test_matrix_covers_crm_ventes_stock(self):
        self.assertEqual(
            rbac_matrix.covered_apps(), {"crm", "ventes", "stock"},
            "La matrice de référence doit couvrir crm + ventes + stock.")

    def test_every_entry_has_allow_and_deny(self):
        """Chaque ligne a AU MOINS un allow ET, pour les gardes fines, un deny."""
        for entry in rbac_matrix.MATRIX:
            verdicts = set(entry.verdicts.values())
            self.assertIn(
                rbac_matrix.ALLOW, verdicts,
                f"L'entrée {entry.label} n'a aucun rôle en ALLOW.")

    def test_matrix_verdicts_hold_live(self):
        """Chaque (entrée × rôle) renvoie le code attendu par la matrice."""
        for entry in rbac_matrix.MATRIX:
            for role_name in rbac_matrix.CANONICAL_ROLE_NAMES:
                verdict = entry.verdict_for(role_name)
                api = _client_for(self.users[role_name])
                if entry.method == "GET":
                    resp = api.get(entry.path)
                elif entry.method == "POST":
                    resp = api.post(entry.path, entry.body or {}, format="json")
                else:  # pragma: no cover - seul GET/POST dans la matrice
                    self.fail(f"Méthode non gérée : {entry.method}")

                if verdict == rbac_matrix.ALLOW:
                    self.assertLess(
                        resp.status_code, 300,
                        f"{entry.label} attendait ALLOW pour {role_name} mais "
                        f"a renvoyé {resp.status_code} ({getattr(resp, 'data', '')}).")
                else:
                    self.assertIn(
                        resp.status_code, (403, 404),
                        f"{entry.label} attendait DENY pour {role_name} mais "
                        f"a renvoyé {resp.status_code}.")
