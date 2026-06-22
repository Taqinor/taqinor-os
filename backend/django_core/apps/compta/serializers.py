"""Sérialiseurs de la Comptabilité générale.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import (
    CompteComptable, CompteTresorerie, EcritureComptable, ExerciceComptable,
    Immobilisation, Journal, LigneEcriture, PeriodeComptable, PlanComptable,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class PlanComptableSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComptable
        fields = ['id', 'code', 'libelle', 'actif', 'date_creation']
        read_only_fields = ['date_creation']


class CompteComptableSerializer(serializers.ModelSerializer):
    classe_display = serializers.CharField(
        source='get_classe_display', read_only=True)

    class Meta:
        model = CompteComptable
        fields = [
            'id', 'plan', 'numero', 'intitule', 'classe', 'classe_display',
            'sens', 'est_tiers', 'lettrable', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_plan(self, value):
        return _meme_societe(self, value, 'Plan')


class JournalSerializer(serializers.ModelSerializer):
    type_journal_display = serializers.CharField(
        source='get_type_journal_display', read_only=True)

    class Meta:
        model = Journal
        fields = [
            'id', 'code', 'libelle', 'type_journal', 'type_journal_display',
            'compte_contrepartie', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_compte_contrepartie(self, value):
        return _meme_societe(self, value, 'Compte')


class LigneEcritureSerializer(serializers.ModelSerializer):
    compte_numero = serializers.CharField(
        source='compte.numero', read_only=True)
    compte_intitule = serializers.CharField(
        source='compte.intitule', read_only=True)

    class Meta:
        model = LigneEcriture
        fields = [
            'id', 'compte', 'compte_numero', 'compte_intitule', 'libelle',
            'debit', 'credit', 'lettrage', 'tiers_type', 'tiers_id',
        ]

    def validate_compte(self, value):
        return _meme_societe(self, value, 'Compte')


class EcritureComptableSerializer(serializers.ModelSerializer):
    lignes = LigneEcritureSerializer(many=True)
    journal_code = serializers.CharField(source='journal.code', read_only=True)
    total_debit = serializers.SerializerMethodField()
    total_credit = serializers.SerializerMethodField()

    class Meta:
        model = EcritureComptable
        fields = [
            'id', 'journal', 'journal_code', 'reference', 'date_ecriture',
            'libelle', 'statut', 'source_type', 'source_id', 'lignes',
            'total_debit', 'total_credit', 'date_creation',
        ]
        read_only_fields = [
            'date_creation', 'source_type', 'source_id', 'total_debit',
            'total_credit',
        ]

    def get_total_debit(self, obj):
        return obj.total_debit

    def get_total_credit(self, obj):
        return obj.total_credit

    def validate_journal(self, value):
        return _meme_societe(self, value, 'Journal')

    def validate(self, attrs):
        # Équilibre exigé à la création/maj : Σ débit = Σ crédit.
        lignes = attrs.get('lignes')
        if lignes is not None:
            if len(lignes) < 2:
                raise serializers.ValidationError(
                    "Une écriture doit comporter au moins deux lignes.")
            debit = sum((Decimal(lig.get('debit') or 0) for lig in lignes),
                        Decimal('0'))
            credit = sum((Decimal(lig.get('credit') or 0) for lig in lignes),
                         Decimal('0'))
            if debit != credit:
                raise serializers.ValidationError(
                    "L'écriture doit être équilibrée : "
                    f"Σ débit ({debit}) ≠ Σ crédit ({credit}).")
        return attrs

    def create(self, validated_data):
        lignes = validated_data.pop('lignes')
        company = validated_data['company']
        ecriture = EcritureComptable.objects.create(**validated_data)
        for ligne in lignes:
            LigneEcriture.objects.create(
                ecriture=ecriture, company=company, **ligne)
        return ecriture

    def update(self, instance, validated_data):
        lignes = validated_data.pop('lignes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lignes is not None:
            instance.lignes.all().delete()
            for ligne in lignes:
                LigneEcriture.objects.create(
                    ecriture=instance, company=instance.company, **ligne)
        return instance


class CompteTresorerieSerializer(serializers.ModelSerializer):
    type_compte_display = serializers.CharField(
        source='get_type_compte_display', read_only=True)
    compte_numero = serializers.CharField(
        source='compte_comptable.numero', read_only=True)

    class Meta:
        model = CompteTresorerie
        fields = [
            'id', 'type_compte', 'type_compte_display', 'libelle', 'banque',
            'rib', 'iban', 'swift', 'devise', 'solde_initial',
            'compte_comptable', 'compte_numero', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_compte_comptable(self, value):
        return _meme_societe(self, value, 'Compte comptable')


class ExerciceComptableSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = ExerciceComptable
        fields = [
            'id', 'libelle', 'date_debut', 'date_fin', 'statut',
            'statut_display', 'an_reporte', 'date_cloture', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'an_reporte', 'date_cloture', 'date_creation']

    def validate(self, attrs):
        debut = attrs.get('date_debut')
        fin = attrs.get('date_fin')
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                "La date de fin doit être postérieure à la date de début.")
        return attrs


class PeriodeComptableSerializer(serializers.ModelSerializer):
    type_periode_display = serializers.CharField(
        source='get_type_periode_display', read_only=True)

    class Meta:
        model = PeriodeComptable
        fields = [
            'id', 'exercice', 'type_periode', 'type_periode_display',
            'libelle', 'date_debut', 'date_fin', 'verrouillee',
            'date_verrouillage', 'date_creation',
        ]
        read_only_fields = [
            'verrouillee', 'date_verrouillage', 'date_creation']

    def validate_exercice(self, value):
        return _meme_societe(self, value, 'Exercice')

    def validate(self, attrs):
        debut = attrs.get('date_debut')
        fin = attrs.get('date_fin')
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                "La date de fin doit être postérieure à la date de début.")
        return attrs


class ImmobilisationSerializer(serializers.ModelSerializer):
    """Sérialiseur du registre des immobilisations (FG118).

    ``company`` posée côté serveur (jamais du corps). Expose la TVA et le coût
    TTC dérivés en lecture seule.
    """
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    montant_tva = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    cout_ttc = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Immobilisation
        fields = [
            'id', 'reference', 'libelle', 'categorie', 'categorie_display',
            'cout', 'taux_tva', 'montant_tva', 'cout_ttc', 'date_acquisition',
            'actif', 'date_creation',
        ]
        read_only_fields = [
            'montant_tva', 'cout_ttc', 'date_creation']

    def validate_cout(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le coût d'acquisition doit être positif.")
        return value

    def validate_taux_tva(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le taux de TVA doit être positif.")
        return value
