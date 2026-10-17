"""Champs déclarés d'une ligne de facture fournisseur (extraits de ``serializers.py``, C20)."""
import re
from decimal import Decimal

from rest_framework import serializers

from core.champs_stricts import DecimalBornee


class TauxTvaLigne(DecimalBornee):
    r"""ENF11 nocturne - ``lignes[].taux_tva`` : chaine au motif EXACT publie
    (``\d{1,3}`` entiers ASCII, <= 2 decimales), 0..100. ``DecimalField``
    de DRF lit aussi `` 5 ``, ``1e1`` ou des chiffres non ASCII, que le schema
    declare invalides : on applique le motif avant la conversion."""

    _MOTIF = re.compile(r'(?:\d{1,3}(?:\.\d{0,2})?|\.\d{1,2})', re.ASCII)

    def to_internal_value(self, data):
        if not isinstance(data, str) or not self._MOTIF.fullmatch(data):
            self.fail('invalid')
        return super().to_internal_value(data)


class ChampsLigneFactureFournisseur(serializers.Serializer):
    """Champs declares de ``LigneFactureFournisseurSerializer`` (lecture
    seule + ``taux_tva`` strict)."""

    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None, allow_null=True)
    total_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    # XPUR17 — TVA par ligne (taux marocains). total_tva = 0 si taux_tva vide
    # (ligne historique, suit le taux global agrégé de la facture).
    total_tva = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    taux_tva = TauxTvaLigne(
        max_digits=5, decimal_places=2, min_value=Decimal('0'),
        max_value=Decimal('100'), required=False, allow_null=True)
