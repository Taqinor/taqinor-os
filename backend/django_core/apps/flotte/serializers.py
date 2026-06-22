"""Sérialiseurs du module Gestion de flotte.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par le
``TenantMixin`` (``perform_create``). Aucune valeur de société du corps de requête
n'est jamais acceptée (multi-tenant).
"""
from rest_framework import serializers

from .models import EnginRoulant, ReferentielFlotte, Vehicule


class VehiculeSerializer(serializers.ModelSerializer):
    energie_display = serializers.CharField(
        source='get_energie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # FLOTTE3 — libellé en lecture de l'emplacement de stock lié (résolu via le
    # sélecteur de `apps.stock`, dégrade sur l'id nu).
    emplacement_stock_label = serializers.SerializerMethodField()

    class Meta:
        model = Vehicule
        fields = [
            'id', 'immatriculation', 'marque', 'modele', 'energie',
            'energie_display', 'kilometrage', 'valeur', 'statut',
            'statut_display', 'emplacement_stock_id', 'emplacement_stock_label',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_emplacement_stock_label(self, obj):
        from .selectors import emplacement_stock_label
        return emplacement_stock_label(
            obj.company, obj.emplacement_stock_id)

    def validate_emplacement_stock_id(self, value):
        """FLOTTE3 — Valide (best-effort) que l'id pointe un EmplacementStock de
        la MÊME société, via le sélecteur de `apps.stock` (import local, jamais
        `apps.stock.models`). Si le sélecteur est indisponible, dégrade : on
        stocke l'id sans valider (comportement de la lane PROJ2)."""
        if value in (None, ''):
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        try:
            from apps.stock import selectors as stock_selectors
        except Exception:
            return value
        getter = getattr(stock_selectors, 'get_emplacement_scoped', None)
        if getter is None:
            # Le stock n'expose pas de sélecteur adapté : on dégrade (store-only).
            return value
        if getter(company, value) is None:
            raise serializers.ValidationError(
                "Emplacement de stock introuvable pour cette société.")
        return value


class EnginRoulantSerializer(serializers.ModelSerializer):
    type_engin_display = serializers.CharField(
        source='get_type_engin_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = EnginRoulant
        fields = [
            'id', 'nom', 'type_engin', 'type_engin_display', 'marque',
            'modele', 'compteur_heures', 'valeur', 'statut', 'statut_display',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class ReferentielFlotteSerializer(serializers.ModelSerializer):
    """FLOTTE6 — entrée d'une liste de référence éditable du parc.

    ``company`` n'est jamais exposée en écriture : elle est posée côté serveur
    par le ``TenantMixin``. L'unicité ``(company, domaine, code)`` est validée
    par société (le scope société est appliqué dans le sérialiseur, jamais lu du
    corps de requête)."""

    domaine_display = serializers.CharField(
        source='get_domaine_display', read_only=True)

    class Meta:
        model = ReferentielFlotte
        fields = [
            'id', 'domaine', 'domaine_display', 'code', 'libelle', 'ordre',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        """Vérifie l'unicité (company, domaine, code) DANS la société courante.

        Le ``UniqueTogetherValidator`` par défaut inclut ``company``, absent des
        champs exposés ; on revalide donc explicitement avec la société du
        serveur pour renvoyer une 400 lisible plutôt qu'une 500 d'intégrité."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return attrs
        domaine = attrs.get('domaine', getattr(self.instance, 'domaine', None))
        code = attrs.get('code', getattr(self.instance, 'code', None))
        qs = ReferentielFlotte.objects.filter(
            company=company, domaine=domaine, code=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'code': "Ce code existe déjà pour ce domaine."})
        return attrs
