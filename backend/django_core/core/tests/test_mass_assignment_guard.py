"""YRBAC8 — ServerControlledFieldsMixin : les champs de gouvernance sont ignorés.

Exerce le mixin sur un sérialiseur SYNTHÉTIQUE : injecter ``company``,
``is_superuser``, ``role`` ou ``created_by`` dans le body est IGNORÉ (retiré
avant validation), tandis que les champs métier légitimes passent.
"""
from django.http import QueryDict
from django.test import SimpleTestCase
from rest_framework import serializers

from core.serializer_mixins import (
    DEFAULT_SERVER_CONTROLLED_FIELDS,
    ServerControlledFieldsMixin,
)


class _GuardedSerializer(ServerControlledFieldsMixin, serializers.Serializer):
    nom = serializers.CharField()
    prix = serializers.IntegerField(required=False, default=0)
    server_controlled_fields = frozenset({"statut"})


class MassAssignmentGuardTests(SimpleTestCase):
    def test_governance_fields_are_stripped_from_body(self):
        payload = {
            "nom": "Devis X",
            "prix": 100,
            "company": 999,
            "is_superuser": True,
            "role": 42,
            "created_by": 7,
        }
        ser = _GuardedSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertNotIn("company", ser.validated_data)
        self.assertNotIn("is_superuser", ser.validated_data)
        self.assertNotIn("role", ser.validated_data)
        self.assertNotIn("created_by", ser.validated_data)
        self.assertEqual(ser.validated_data["nom"], "Devis X")
        self.assertEqual(ser.validated_data["prix"], 100)

    def test_custom_server_controlled_field_is_stripped(self):
        ser = _GuardedSerializer(data={"nom": "Y", "statut": "valide"})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertNotIn("statut", ser.validated_data)

    def test_default_registry_covers_key_governance_fields(self):
        for f in ("company", "created_by", "is_superuser", "role", "owner"):
            self.assertIn(f, DEFAULT_SERVER_CONTROLLED_FIELDS)

    def test_immutable_querydict_is_handled(self):
        qd = QueryDict(mutable=True)
        qd["nom"] = "Z"
        qd["company"] = "5"
        qd._mutable = False
        ser = _GuardedSerializer(data=qd)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertNotIn("company", ser.validated_data)
        self.assertEqual(ser.validated_data["nom"], "Z")

    def test_clean_body_unaffected(self):
        ser = _GuardedSerializer(data={"nom": "OK", "prix": 5})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["nom"], "OK")
        self.assertEqual(ser.validated_data["prix"], 5)
