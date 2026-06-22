"""Sérialiseurs de la Paie marocaine.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import BaremeIR, ParametrePaie, Rubrique, TrancheIR


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class ParametrePaieSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametrePaie
        fields = [
            'id', 'date_effet', 'smig', 'smag', 'plafond_cnss',
            'taux_cnss_salarial', 'taux_cnss_patronal', 'taux_amo_salarial',
            'taux_amo_patronal', 'taux_formation_pro',
            'seuil_frais_pro', 'taux_frais_pro_bas', 'plafond_frais_pro_bas',
            'taux_frais_pro_haut', 'plafond_frais_pro_haut',
            'deduction_par_personne_a_charge', 'plafond_personnes_a_charge',
            'actif', 'valide_par_fondateur', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class RubriqueSerializer(serializers.ModelSerializer):
    """Sérialiseur de la rubrique paramétrable (PAIE6).

    ``company`` n'est jamais exposée : posée côté serveur par le
    ``TenantMixin``. Le couple ``(company, code)`` étant unique, l'unicité du
    ``code`` est validée à l'enregistrement (DB) ; ``code`` reste éditable.
    """
    class Meta:
        model = Rubrique
        fields = [
            'id', 'code', 'libelle', 'type', 'imposable', 'soumis_cnss',
            'soumis_amo', 'soumis_cimr', 'compte', 'base', 'taux',
            'montant_fixe', 'ordre', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_code(self, value):
        """``code`` unique par société (``company`` posée côté serveur).

        ``company`` n'étant pas un champ du sérialiseur, DRF n'ajoute pas le
        ``UniqueTogetherValidator`` automatique : on vérifie l'unicité ici pour
        renvoyer un 400 propre plutôt qu'une ``IntegrityError`` 500.
        """
        request = self.context.get('request')
        if request is None:
            return value
        qs = Rubrique.objects.filter(
            company=request.user.company_id, code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'Une rubrique avec ce code existe déjà.')
        return value


class TrancheIRSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrancheIR
        fields = [
            'id', 'borne_min', 'borne_max', 'taux', 'somme_a_deduire', 'ordre',
        ]


class BaremeIRSerializer(serializers.ModelSerializer):
    tranches = TrancheIRSerializer(many=True)

    class Meta:
        model = BaremeIR
        fields = [
            'id', 'libelle', 'date_effet', 'actif', 'valide_par_fondateur',
            'tranches', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def create(self, validated_data):
        tranches = validated_data.pop('tranches', [])
        company = validated_data['company']
        bareme = BaremeIR.objects.create(**validated_data)
        for tranche in tranches:
            TrancheIR.objects.create(
                bareme=bareme, company=company, **tranche)
        return bareme

    def update(self, instance, validated_data):
        tranches = validated_data.pop('tranches', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tranches is not None:
            instance.tranches.all().delete()
            for tranche in tranches:
                TrancheIR.objects.create(
                    bareme=instance, company=instance.company, **tranche)
        return instance
