"""api-fuzz-full 24/10/2026 — bornes PUBLIÉES des sérialiseurs installations,
hors du fichier-mur ``serializers.py`` (règle C20 : il ne grossit pas).

Chaque mixin est un ``Serializer`` (et non un mixin nu) : la métaclasse DRF ne
collecte ``_declared_fields`` que sur des bases qui en portent.
"""
from decimal import Decimal

from rest_framework import serializers

from core.champs_stricts import ChaineStricte, DecimalBornee


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
