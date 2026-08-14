"""Sérialiseurs de l'app CPQ.

``company`` n'est jamais exposée en écriture : posée côté serveur par le
``TenantMixin`` (``perform_create``)."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from django.db import transaction

from core.rules import validate_condition_group
from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ,
    OffreGroupee, LigneOffreGroupee, PrixContractuel,
    QuestionConfigurateur, SeuilMargeFamille, RegleApprobationRemise,
    ClauseCGV, ProduitEquivalent, ParametresCPQ,
)


class OptionProduitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionProduit
        fields = ['id', 'produit', 'groupe_option', 'obligatoire']


class ContrainteCompatibiliteSerializer(serializers.ModelSerializer):
    bloquante = serializers.BooleanField(read_only=True)

    class Meta:
        model = ContrainteCompatibilite
        fields = ['id', 'produit_a', 'produit_b', 'type',
                  'message_utilisateur', 'bloquante']


class RegleProduitCPQSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegleProduitCPQ
        fields = ['id', 'nom', 'condition_group', 'actions', 'bloquante',
                  'actif', 'date_creation']
        read_only_fields = ['date_creation']

    def validate_condition_group(self, value):
        """Valide la STRUCTURE de l'arbre via le moteur générique (core.rules)
        avant persistance — jamais un nouveau moteur."""
        errors = validate_condition_group(value)
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate_actions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'actions doit être une liste.')
        return value


class LigneOffreGroupeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneOffreGroupee
        fields = ['id', 'produit', 'quantite', 'mode_prix', 'valeur']


class OffreGroupeeSerializer(serializers.ModelSerializer):
    lignes = LigneOffreGroupeeSerializer(many=True, required=False)

    class Meta:
        model = OffreGroupee
        fields = ['id', 'nom', 'prix_total', 'actif', 'date_creation',
                  'lignes']
        read_only_fields = ['date_creation']

    @transaction.atomic
    def create(self, validated_data):
        lignes = validated_data.pop('lignes', [])
        offre = OffreGroupee.objects.create(**validated_data)
        for ligne in lignes:
            LigneOffreGroupee.objects.create(offre=offre, **ligne)
        return offre

    @transaction.atomic
    def update(self, instance, validated_data):
        lignes = validated_data.pop('lignes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lignes is not None:
            instance.lignes.all().delete()
            for ligne in lignes:
                LigneOffreGroupee.objects.create(offre=instance, **ligne)
        return instance


class PrixContractuelSerializer(serializers.ModelSerializer):
    est_actif = serializers.BooleanField(read_only=True)

    class Meta:
        model = PrixContractuel
        fields = ['id', 'client', 'produit', 'prix_ht', 'date_debut',
                  'date_fin', 'motif', 'created_by', 'date_creation',
                  'est_actif']
        read_only_fields = ['created_by', 'date_creation']


class QuestionConfigurateurSerializer(serializers.ModelSerializer):
    champ = serializers.CharField(read_only=True)

    class Meta:
        model = QuestionConfigurateur
        fields = ['id', 'ordre', 'texte', 'type', 'options', 'actif', 'champ']


class SeuilMargeFamilleSerializer(serializers.ModelSerializer):
    """WIR105 — CRUD du garde-fou de marge par famille (NTCPQ6).

    ``categorie`` est validée même-société ; ``company`` posée côté serveur."""
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default=None)

    class Meta:
        model = SeuilMargeFamille
        fields = ['id', 'categorie', 'categorie_nom', 'marge_min_pct']

    def validate_categorie(self, categorie):
        request = self.context.get('request')
        if request is not None and categorie is not None \
                and categorie.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cette catégorie n'appartient pas à votre société.")
        return categorie


class RegleApprobationRemiseSerializer(serializers.ModelSerializer):
    """WIR105 — CRUD des paliers d'approbation par profondeur de remise
    (NTCPQ7/8). ``company`` posée côté serveur."""
    niveau_approbation_display = serializers.CharField(
        source='get_niveau_approbation_display', read_only=True)

    class Meta:
        model = RegleApprobationRemise
        fields = [
            'id', 'libelle', 'remise_min_pct', 'remise_max_pct',
            'niveau_approbation', 'niveau_approbation_display',
            'nombre_approbateurs', 'priorite', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        """Bornes cohérentes : si les deux bornes sont fournies,
        ``remise_min_pct`` ≤ ``remise_max_pct``."""
        lo = attrs.get('remise_min_pct')
        hi = attrs.get('remise_max_pct')
        if self.instance is not None:
            lo = lo if 'remise_min_pct' in attrs else self.instance.remise_min_pct
            hi = hi if 'remise_max_pct' in attrs else self.instance.remise_max_pct
        if lo is not None and hi is not None and lo > hi:
            raise serializers.ValidationError({
                'remise_max_pct':
                    'La borne max doit être ≥ la borne min.'})
        return attrs


class ProduitEquivalentSerializer(serializers.ModelSerializer):
    """NTCPQ16 — Règle de substitution produit par tier. ``company`` posée côté
    serveur ; les deux produits sont validés même-société."""
    produit_source_nom = serializers.CharField(
        source='produit_source.nom', read_only=True, default=None)
    produit_substitut_nom = serializers.CharField(
        source='produit_substitut.nom', read_only=True, default=None)

    class Meta:
        model = ProduitEquivalent
        fields = ['id', 'produit_source', 'produit_source_nom',
                  'produit_substitut', 'produit_substitut_nom', 'tier',
                  'actif']

    def _meme_societe(self, produit):
        request = self.context.get('request')
        if request is not None and produit is not None \
                and produit.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce produit n'appartient pas à votre société.")
        return produit

    def validate_produit_source(self, produit):
        return self._meme_societe(produit)

    def validate_produit_substitut(self, produit):
        return self._meme_societe(produit)


class ParametresCPQSerializer(serializers.ModelSerializer):
    """NTCPQ30 — Réglages CPQ singleton. ``company`` posée côté serveur."""

    class Meta:
        model = ParametresCPQ
        fields = [
            'id', 'marge_min_defaut_pct', 'approbation_active',
            'variantes_auto_generees', 'duree_validite_prix_contractuel_jours',
            'compatibilite_mode', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class ClauseCGVSerializer(serializers.ModelSerializer):
    """NTCPQ11/12 — Bibliothèque de clauses réutilisables.

    ``condition_lisible`` rend la condition en langage clair (ex.
    « type_deal=industriel ET montant>500000 ») pour l'écran Paramètres.
    ``company`` est posée côté serveur (jamais lue du corps)."""
    condition_lisible = serializers.SerializerMethodField()

    class Meta:
        model = ClauseCGV
        fields = ['id', 'nom', 'corps_texte', 'type_deal', 'applicable_si',
                  'condition_lisible', 'ordre', 'actif', 'date_creation']
        read_only_fields = ['date_creation']

    @extend_schema_field(serializers.CharField())
    def get_condition_lisible(self, obj):
        from .selectors import condition_en_clair
        base = condition_en_clair(obj.applicable_si)
        if obj.type_deal:
            prefixe = f'type_deal={obj.type_deal}'
            return prefixe if base == 'toujours' else f'{prefixe} ET {base}'
        return base

    def validate_applicable_si(self, value):
        """Valide la STRUCTURE de l'arbre via le moteur générique
        (``core.rules``) — jamais un nouveau moteur. Vide = toujours vrai."""
        if not value:
            return value or {}
        errors = validate_condition_group(value)
        if errors:
            raise serializers.ValidationError(errors)
        return value
