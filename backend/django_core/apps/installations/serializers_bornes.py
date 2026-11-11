"""api-fuzz-full 24/10/2026 — bornes PUBLIÉES des sérialiseurs installations,
hors du fichier-mur ``serializers.py`` (règle C20 : il ne grossit pas).

Chaque mixin est un ``Serializer`` (et non un mixin nu) : la métaclasse DRF ne
collecte ``_declared_fields`` que sur des bases qui en portent.
"""
from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import ChaineStricte, DecimalBornee
from core.conflit_etat import ConflitEtat


class SeuilResponsableBorneMixin(serializers.Serializer):
    """Borne basse PUBLIÉE (motif sans signe « - »)."""
    seuil_responsable = DecimalBornee(
        max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False)


class MontantProvisionBorneMixin(serializers.Serializer):
    """Borne basse PUBLIÉE (motif sans signe « - »)."""
    montant_provision = DecimalBornee(
        max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False)


class MotifSansNulMixin(serializers.Serializer):
    """Texte strict, sans caractère nul (publié au schéma)."""
    motif = ChaineStricte(required=False, allow_blank=True, allow_null=True)


class CautionUnitaireBorneMixin(serializers.Serializer):
    """Caution ≥ 0 PUBLIÉE : une caution négative faisait un produit négatif hors
    bornes → 500 à la sérialisation de ``caution_totale``."""
    caution_unitaire = DecimalBornee(
        max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False)


class PrixEstimeNonNegatifMixin:
    """ACHT11 — prix estimé fini et non négatif. api-fuzz full : le motif publié
    d'un décimal souple ne sait pas exclure le signe ``-`` -> refus d'ÉTAT
    (409), comme la quantité."""

    def validate_prix_estime(self, value):
        if value is not None and (not value.is_finite() or value < 0):
            raise ConflitEtat(
                {'prix_estime': ['Le prix estimé ne peut pas être négatif.']})
        return value


@extend_schema_field({'type': 'object', 'additionalProperties': True, 'nullable': True})
class CustomDataObjet(serializers.JSONField):
    """``custom_data`` d'un chantier : un OBJET ou ``null`` (sa clé interne
    ``date_reception_defaite`` y est reprise, ACSV113) — un tableau est refusé
    400 au lieu d'un 500 (api-fuzz, PR #1355)."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Objet « clé : valeur » attendu.')
        return super().to_internal_value(data)


class CustomDataObjetMixin(serializers.Serializer):
    """Publie et valide ``custom_data`` comme un objet (voir ci-dessus)."""
    custom_data = CustomDataObjet(required=False, allow_null=True)
