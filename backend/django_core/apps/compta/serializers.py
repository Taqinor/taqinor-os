"""Sérialiseurs de la Comptabilité générale.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import (
    CessionImmobilisation, CompteComptable, CompteTresorerie,
    DotationAmortissement, EcritureComptable, ExerciceComptable,
    Immobilisation, Journal, LigneEcriture, LigneReleve, PeriodeComptable,
    PlanAmortissement, PlanComptable, RapprochementBancaire,
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


class DotationAmortissementSerializer(serializers.ModelSerializer):
    """Dotation d'amortissement d'un exercice (FG119) — lecture seule.

    Les dotations sont CALCULÉES par le service à partir du plan, jamais saisies
    à la main. Ce sérialiseur ne sert qu'à les restituer (et l'écriture postée).
    """
    class Meta:
        model = DotationAmortissement
        fields = [
            'id', 'plan', 'annee', 'date_dotation', 'montant', 'cumul',
            'valeur_nette', 'posted', 'ecriture', 'date_creation',
        ]
        read_only_fields = fields


class PlanAmortissementSerializer(serializers.ModelSerializer):
    """Plan d'amortissement d'une immobilisation (FG119).

    ``company`` posée côté serveur. Expose le calendrier de dotations imbriqué
    (lecture seule) et le taux linéaire dérivé. La création/maj passe par
    l'action ``plan-amortissement`` de l'immobilisation (service idempotent).
    """
    mode_display = serializers.CharField(
        source='get_mode_display', read_only=True)
    taux_lineaire = serializers.DecimalField(
        max_digits=8, decimal_places=4, read_only=True)
    dotations = DotationAmortissementSerializer(many=True, read_only=True)

    class Meta:
        model = PlanAmortissement
        fields = [
            'id', 'immobilisation', 'mode', 'mode_display', 'duree_annees',
            'base_amortissable', 'date_debut', 'coefficient_degressif',
            'taux_lineaire', 'compte_dotation', 'compte_amortissement',
            'dotations', 'date_creation',
        ]
        read_only_fields = [
            'coefficient_degressif', 'taux_lineaire', 'dotations',
            'date_creation',
        ]

    def validate_immobilisation(self, value):
        return _meme_societe(self, value, 'Immobilisation')

    def validate_duree_annees(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "La durée d'amortissement doit être d'au moins 1 an.")
        return value


class CessionImmobilisationSerializer(serializers.ModelSerializer):
    """Cession / mise au rebut d'une immobilisation (FG120) — lecture seule.

    Les cessions sont CALCULÉES et enregistrées par le service (action
    ``ceder`` de l'immobilisation), jamais saisies à la main : VNC, cumul
    d'amortissement et résultat de cession sont figés côté serveur. Expose les
    plus/moins-values dérivées et l'écriture postée.
    """
    type_cession_display = serializers.CharField(
        source='get_type_cession_display', read_only=True)
    immobilisation_libelle = serializers.CharField(
        source='immobilisation.libelle', read_only=True)
    plus_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    moins_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = CessionImmobilisation
        fields = [
            'id', 'immobilisation', 'immobilisation_libelle', 'type_cession',
            'type_cession_display', 'date_cession', 'prix_cession',
            'amortissements_cumules', 'valeur_nette_comptable',
            'resultat_cession', 'plus_value', 'moins_value', 'posted',
            'ecriture', 'date_creation',
        ]
        read_only_fields = fields


class LigneReleveSerializer(serializers.ModelSerializer):
    """Ligne d'un relevé bancaire (FG123).

    ``company``/``rapprochement`` posés côté serveur. Expose en lecture seule le
    montant GL pointé, l'écart et le statut de concordance dérivés ; les lignes
    GL appariées sont restituées en IDs.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    montant_pointe = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    ecart = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    est_concordante = serializers.BooleanField(read_only=True)
    lignes_gl = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True)

    class Meta:
        model = LigneReleve
        fields = [
            'id', 'rapprochement', 'date_operation', 'libelle', 'reference',
            'montant', 'statut', 'statut_display', 'lignes_gl',
            'montant_pointe', 'ecart', 'est_concordante', 'date_creation',
        ]
        read_only_fields = [
            'rapprochement', 'statut', 'statut_display', 'lignes_gl',
            'montant_pointe', 'ecart', 'est_concordante', 'date_creation',
        ]


class RapprochementBancaireSerializer(serializers.ModelSerializer):
    """Rapprochement bancaire d'un compte de trésorerie (FG123).

    ``company`` posée côté serveur (jamais du corps). ``compte_tresorerie`` est
    validé comme appartenant à la société. Expose les lignes de relevé imbriquées
    et l'indicateur ``est_rapproche`` en lecture seule.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    compte_libelle = serializers.CharField(
        source='compte_tresorerie.libelle', read_only=True)
    lignes_releve = LigneReleveSerializer(many=True, read_only=True)
    est_rapproche = serializers.BooleanField(read_only=True)

    class Meta:
        model = RapprochementBancaire
        fields = [
            'id', 'compte_tresorerie', 'compte_libelle', 'libelle',
            'date_debut', 'date_fin', 'date_releve', 'solde_releve', 'statut',
            'statut_display', 'date_rapprochement', 'lignes_releve',
            'est_rapproche', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'statut_display', 'date_rapprochement', 'lignes_releve',
            'est_rapproche', 'date_creation',
        ]

    def validate_compte_tresorerie(self, value):
        return _meme_societe(self, value, 'Compte de trésorerie')

    def validate(self, attrs):
        debut = attrs.get('date_debut')
        fin = attrs.get('date_fin')
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                "La date de fin doit être postérieure à la date de début.")
        return attrs
