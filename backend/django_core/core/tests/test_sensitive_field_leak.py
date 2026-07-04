"""YRBAC6 — balayage anti-fuite champ-sensible (pan-sérialiseur/export).

Deux gardes :

1. **Runtime** — rend la fiche produit (``stock.ProduitSerializer``) en tant
   que rôle bas privilège et vérifie que ``prix_achat``/``marge`` sont ABSENTS
   du payload (retirés, pas mis à null).
2. **Statique (drift)** — scanne les ``serializers.py`` des apps et échoue si un
   ``ModelSerializer`` déclare un champ de ``core.permissions.SENSITIVE_FIELDS``
   dans son ``Meta.fields`` SANS aucune logique de masquage (``get_fields`` /
   ``pop``/ garde par permission) dans le même fichier — attrape une NOUVELLE
   exposition non masquée.
"""
import ast
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from core.permissions import SENSITIVE_FIELDS

User = get_user_model()

DJANGO_CORE_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = DJANGO_CORE_ROOT / "apps"


class SensitiveRegistryTests(TestCase):
    def test_registry_is_central_and_non_empty(self):
        self.assertGreater(len(SENSITIVE_FIELDS), 0)
        self.assertIn("prix_achat", SENSITIVE_FIELDS)
        self.assertEqual(SENSITIVE_FIELDS["prix_achat"], "prix_achat_voir")


class ProduitLeakTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug="yrbac6", defaults={"nom": "YRBAC6"})[0]

    def test_low_priv_role_never_sees_prix_achat_or_marge(self):
        from apps.stock.models import Produit
        from apps.stock.serializers import ProduitSerializer
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request

        role = Role.objects.create(
            company=self.company, nom="lecteur-stock",
            permissions=["stock_voir"])
        user = User.objects.create_user(
            username="yrbac6-low", password="x", role=role,
            company=self.company)
        produit = Produit.objects.create(
            company=self.company, nom="Panneau", prix_vente=1000,
            prix_achat=600)

        req = Request(APIRequestFactory().get("/"))
        req.user = user
        data = ProduitSerializer(produit, context={"request": req}).data
        # prix_achat et l'indicateur de marge doivent être ABSENTS (retirés).
        self.assertNotIn("prix_achat", data)
        self.assertNotIn("marge_pct", data)
        # Confirme aussi qu'un rôle AUTORISÉ voit bien prix_achat (le masquage
        # est ciblé, pas un retrait systématique).
        priv_role = Role.objects.create(
            company=self.company, nom="dir-stock",
            permissions=["stock_voir", "prix_achat_voir", "marge_voir"])
        priv = User.objects.create_user(
            username="yrbac6-priv", password="x", role=priv_role,
            company=self.company)
        req2 = Request(APIRequestFactory().get("/"))
        req2.user = priv
        data2 = ProduitSerializer(produit, context={"request": req2}).data
        self.assertIn("prix_achat", data2)


class SensitiveSerializerStaticSweepTests(TestCase):
    """Drift statique : un champ sensible listé sans masquage fait échouer."""

    def test_no_serializer_exposes_a_sensitive_field_without_masking(self):
        offenders = []
        for path in sorted(APPS_ROOT.rglob("serializers.py")):
            if "migrations" in path.parts:
                continue
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            # Le masquage se fait au niveau fichier (get_fields + pop, ou une
            # garde par permission) — on exige AU MOINS une trace de masquage
            # dès qu'un champ sensible est cité comme champ exposé.
            masks = ("get_fields" in source or ".pop(" in source
                     or "_voir" in source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                cited = self._sensitive_fields_in_meta(node)
                if cited and not masks:
                    offenders.append(
                        f"{path.relative_to(DJANGO_CORE_ROOT)}::{node.name} "
                        f"expose {sorted(cited)} sans masquage")
        self.assertEqual(
            offenders, [],
            "Sérialiseurs exposant un champ sensible sans masquage "
            "(ajoutez une garde get_fields/permission, cf. SENSITIVE_FIELDS) :\n"
            + "\n".join(offenders))

    def _sensitive_fields_in_meta(self, class_node):
        """Champs sensibles listés dans un ``Meta.fields = [...]`` explicite."""
        found = set()
        for node in ast.walk(class_node):
            if isinstance(node, ast.ClassDef) and node.name == "Meta":
                for stmt in node.body:
                    if not (isinstance(stmt, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == "fields"
                                    for t in stmt.targets)):
                        continue
                    if isinstance(stmt.value, (ast.List, ast.Tuple)):
                        for elt in stmt.value.elts:
                            if (isinstance(elt, ast.Constant)
                                    and elt.value in SENSITIVE_FIELDS):
                                found.add(elt.value)
        return found
