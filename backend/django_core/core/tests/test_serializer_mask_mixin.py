"""YRBAC7 — SensitiveFieldMaskMixin : masquage réutilisable par permission.

Exerce le mixin sur un sérialiseur SYNTHÉTIQUE (aucune dépendance à une app
métier) : un champ sensible est ABSENT (pas None) sans la permission, PRÉSENT
avec, et jamais masqué sans requête (rendu serveur) ni pour un compte légacy.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from authentication.models import Company
from apps.roles.models import Role
from core.serializer_mixins import (
    SensitiveFieldMaskMixin, SerializerMaskMixin,
)

User = get_user_model()


class _Obj:
    def __init__(self, nom, prix_achat):
        self.nom = nom
        self.prix_achat = prix_achat


class _MaskedSerializer(SensitiveFieldMaskMixin, serializers.Serializer):
    nom = serializers.CharField()
    prix_achat = serializers.IntegerField()
    sensitive_fields = {"prix_achat": "prix_achat_voir"}


class SensitiveFieldMaskMixinTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug="yrbac7", defaults={"nom": "YRBAC7"})[0]
        cls.obj = _Obj("Panneau", 600)

    def _req(self, user):
        r = Request(APIRequestFactory().get("/"))
        r.user = user
        return r

    def _user(self, name, perms):
        role = Role.objects.create(
            company=self.company, nom=name, permissions=perms)
        return User.objects.create_user(
            username=name, password="x", role=role, company=self.company)

    def test_field_absent_without_permission(self):
        user = self._user("no-perm", ["stock_voir"])
        data = _MaskedSerializer(
            self.obj, context={"request": self._req(user)}).data
        self.assertNotIn("prix_achat", data)
        self.assertIn("nom", data)  # champ non sensible conservé

    def test_field_present_with_permission(self):
        user = self._user("with-perm", ["prix_achat_voir"])
        data = _MaskedSerializer(
            self.obj, context={"request": self._req(user)}).data
        self.assertIn("prix_achat", data)
        self.assertEqual(data["prix_achat"], 600)

    def test_not_masked_without_request_context(self):
        # Rendu serveur/interne (pas de request) → rien n'est masqué.
        data = _MaskedSerializer(self.obj).data
        self.assertIn("prix_achat", data)

    def test_legacy_account_without_fine_role_not_masked(self):
        user = User.objects.create_user(
            username="legacy", password="x", company=self.company)  # role=None
        data = _MaskedSerializer(
            self.obj, context={"request": self._req(user)}).data
        self.assertIn("prix_achat", data)

    def test_field_removed_not_nulled(self):
        user = self._user("no-perm2", ["stock_voir"])
        data = _MaskedSerializer(
            self.obj, context={"request": self._req(user)}).data
        # Le champ est retiré, pas mis à None.
        self.assertNotIn("prix_achat", data)
        self.assertIsNotNone(data.get("prix_achat", "sentinel"))


# ── NTDMO9 — SerializerMaskMixin : masquage PII en mode présentation ─────────
class _Contact:
    def __init__(self, email, telephone, adresse, ville):
        self.email = email
        self.telephone = telephone
        self.adresse = adresse
        self.ville = ville


class _ContactSerializer(SerializerMaskMixin, serializers.Serializer):
    email = serializers.CharField()
    telephone = serializers.CharField()
    adresse = serializers.CharField()
    ville = serializers.CharField()


class SerializerMaskMixinNTDMO9Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.obj = _Contact('k@x.ma', '+212612345678', '12 rue X', 'Casablanca')

    def _req(self, user):
        r = Request(APIRequestFactory().get('/'))
        r.user = user
        return r

    def _user(self, company):
        return User.objects.create_user(
            username=f'u-{company.slug}', password='x', company=company)

    def test_masks_when_demo_presentation_active(self):
        company = Company.objects.create(
            nom='Démo9', slug='demo9', est_demo=True,
            mode_presentation_actif=True)
        data = _ContactSerializer(
            self.obj, context={'request': self._req(self._user(company))}).data
        self.assertEqual(data['email'], '***@***')
        self.assertEqual(data['telephone'], '06 ** ** ** **')
        self.assertNotEqual(data['adresse'], '12 rue X')
        # La ville n'est JAMAIS masquée.
        self.assertEqual(data['ville'], 'Casablanca')

    def test_byte_identical_when_flag_false(self):
        company = Company.objects.create(
            nom='Démo-off', slug='demo9off', est_demo=True,
            mode_presentation_actif=False)
        data = _ContactSerializer(
            self.obj, context={'request': self._req(self._user(company))}).data
        self.assertEqual(data['email'], 'k@x.ma')
        self.assertEqual(data['telephone'], '+212612345678')
        self.assertEqual(data['adresse'], '12 rue X')

    def test_non_demo_company_never_masked_even_if_flag_manipulated(self):
        # Société RÉELLE (est_demo=False) avec le drapeau manipulé à True.
        company = Company.objects.create(
            nom='Réelle9', slug='reelle9', est_demo=False,
            mode_presentation_actif=True)
        data = _ContactSerializer(
            self.obj, context={'request': self._req(self._user(company))}).data
        self.assertEqual(data['email'], 'k@x.ma')  # jamais masqué

    def test_not_masked_without_request(self):
        data = _ContactSerializer(self.obj).data
        self.assertEqual(data['email'], 'k@x.ma')
