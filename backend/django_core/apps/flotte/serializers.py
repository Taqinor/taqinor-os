"""Sérialiseurs du module Gestion de flotte.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par le
``TenantMixin`` (``perform_create``). Aucune valeur de société du corps de requête
n'est jamais acceptée (multi-tenant).
"""
from rest_framework import serializers

from .models import (
    ActifFlotte,
    AffectationConducteur,
    Conducteur,
    EnginRoulant,
    ReferentielFlotte,
    Vehicule,
)


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


class ConducteurSerializer(serializers.ModelSerializer):
    """FLOTTE7 — conducteur / chauffeur avec informations de permis.

    ``company`` n'est JAMAIS exposée en écriture (posée côté serveur via
    ``TenantMixin``). ``user`` est facultatif : un conducteur externe sans
    compte ERP peut être enregistré sans liaison utilisateur.

    Champ lecture seule :
    - ``user_display`` : nom complet de l'utilisateur ERP lié, ou ``None``.
    """

    user_display = serializers.SerializerMethodField()

    class Meta:
        model = Conducteur
        fields = [
            'id', 'user', 'user_display', 'nom', 'telephone',
            'numero_permis', 'categorie_permis',
            'date_obtention', 'date_expiration',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_user_display(self, obj):
        if obj.user_id is None:
            return None
        user = obj.user
        full = (
            f'{user.first_name} {user.last_name}'.strip()
            or user.username
        )
        return full

    def validate_user(self, value):
        """Vérifie que l'utilisateur lié appartient à la même société."""
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Cet utilisateur n'appartient pas à votre société.")
        return value


class ActifFlotteSerializer(serializers.ModelSerializer):
    """FLOTTE5 — référence d'actif unifiée (Vehicule | EnginRoulant).

    ``company`` est posée côté serveur par le ``TenantMixin`` — jamais lue du
    corps de requête. Les champs ``vehicule`` et ``engin`` acceptent les ids
    des actifs de la MÊME société ; la validation (exactement l'un des deux)
    est déléguée au modèle (``full_clean`` dans ``save``).

    Champs lecture seule :
    - ``type_actif`` : 'vehicule' | 'engin'
    - ``label``      : désignation lisible de l'actif cible
    """

    type_actif = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)

    class Meta:
        model = ActifFlotte
        fields = [
            'id', 'vehicule', 'engin', 'type_actif', 'label', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        """Vérifie que exactement un des deux FKs est fourni ET que l'actif
        cible appartient à la société courante."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        engin = attrs.get(
            'engin', getattr(self.instance, 'engin', None))

        has_vehicule = vehicule is not None
        has_engin = engin is not None

        if has_vehicule and has_engin:
            raise serializers.ValidationError(
                "Un actif ne peut pointer qu'un véhicule OU un engin, pas les "
                "deux.")
        if not has_vehicule and not has_engin:
            raise serializers.ValidationError(
                "Renseignez soit 'vehicule' soit 'engin'.")

        if company is not None:
            if has_vehicule and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {'vehicule': "Ce véhicule n'appartient pas à votre société."})
            if has_engin and engin.company_id != company.id:
                raise serializers.ValidationError(
                    {'engin': "Cet engin n'appartient pas à votre société."})

        return attrs


class AffectationConducteurSerializer(serializers.ModelSerializer):
    """FLOTTE8 — Affectation datée conducteur ↔ véhicule.

    ``company`` est posée côté serveur par le ``TenantMixin`` (jamais lue du
    corps de requête). Les FKs ``conducteur`` et ``vehicule`` doivent appartenir
    à la même société que l'utilisateur courant. La validation garantit que
    ``date_fin >= date_debut`` quand ``date_fin`` est renseignée.

    Champs lecture seule :
    - ``conducteur_nom``  : nom complet du conducteur.
    - ``vehicule_label``  : immatriculation + marque/modèle du véhicule.
    """

    conducteur_nom = serializers.SerializerMethodField()
    vehicule_label = serializers.SerializerMethodField()

    class Meta:
        model = AffectationConducteur
        fields = [
            "id",
            "conducteur",
            "conducteur_nom",
            "vehicule",
            "vehicule_label",
            "date_debut",
            "date_fin",
            "notes",
            "actif",
            "date_creation",
        ]
        read_only_fields = ["date_creation"]

    def get_conducteur_nom(self, obj):
        return str(obj.conducteur) if obj.conducteur_id else None

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def validate(self, attrs):
        """Valide la plage de dates et l'appartenance à la société courante."""
        request = self.context.get("request")
        company = getattr(getattr(request, "user", None), "company", None)

        conducteur = attrs.get(
            "conducteur", getattr(self.instance, "conducteur", None))
        vehicule = attrs.get(
            "vehicule", getattr(self.instance, "vehicule", None))
        date_debut = attrs.get(
            "date_debut", getattr(self.instance, "date_debut", None))
        date_fin = attrs.get(
            "date_fin", getattr(self.instance, "date_fin", None))

        # Plage de dates : date_fin >= date_debut quand fournie.
        if date_debut is not None and date_fin is not None:
            if date_fin < date_debut:
                raise serializers.ValidationError(
                    {"date_fin": "La date de fin doit être postérieure ou égale"
                     " à la date de début."})

        # Vérification de société sur les FKs.
        if company is not None:
            if conducteur is not None and conducteur.company_id != company.id:
                raise serializers.ValidationError(
                    {"conducteur":
                     "Ce conducteur n'appartient pas à votre société."})
            if vehicule is not None and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {"vehicule":
                     "Ce véhicule n'appartient pas à votre société."})

        return attrs
