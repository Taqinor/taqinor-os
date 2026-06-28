"""Sérialiseurs de la Comptabilité générale.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import (
    BordereauRemise, Caisse, CessionImmobilisation, ClotureCaisse,
    CompteComptable, CompteTresorerie, DotationAmortissement, EcritureComptable,
    Effet, ExerciceComptable, Immobilisation, Journal, LigneEcriture,
    LignePrevisionnelTresorerie, LigneReleve, MouvementCaisse, PeriodeComptable,
    PlanAmortissement, PlanComptable, Rapprochement, RapprochementBancaire,
    VirementInterne,
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


# ── FG124 — Caisse / petty cash (journal d'espèces) ────────────────────────

class CaisseSerializer(serializers.ModelSerializer):
    """Caisse d'espèces (petty cash) — FG124.

    ``company`` posée côté serveur. ``compte_tresorerie`` validé comme
    appartenant à la société ET de type caisse. Expose le solde courant
    théorique dérivé en lecture seule.
    """
    compte_libelle = serializers.CharField(
        source='compte_tresorerie.libelle', read_only=True)
    solde_courant = serializers.SerializerMethodField()

    class Meta:
        model = Caisse
        fields = [
            'id', 'compte_tresorerie', 'compte_libelle', 'libelle',
            'responsable', 'solde_initial', 'solde_courant', 'actif',
            'date_creation',
        ]
        read_only_fields = ['solde_courant', 'date_creation']

    def get_solde_courant(self, obj):
        from . import selectors
        return selectors.solde_caisse_a(obj)

    def validate_compte_tresorerie(self, value):
        value = _meme_societe(self, value, 'Compte de trésorerie')
        if value is not None and value.type_compte != (
                CompteTresorerie.Type.CAISSE):
            raise serializers.ValidationError(
                "Le compte de trésorerie doit être de type « caisse ».")
        return value


class MouvementCaisseSerializer(serializers.ModelSerializer):
    """Mouvement d'une caisse : entrée/sortie d'espèces (FG124).

    ``company``/``caisse`` posés côté serveur (via l'action de la caisse). Le
    montant signé est exposé en lecture seule ; ``posted``/``ecriture`` aussi.
    """
    sens_display = serializers.CharField(
        source='get_sens_display', read_only=True)
    montant_signe = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = MouvementCaisse
        fields = [
            'id', 'caisse', 'sens', 'sens_display', 'date_mouvement',
            'montant', 'montant_signe', 'motif', 'justificatif', 'piece',
            'compte_contrepartie', 'posted', 'ecriture', 'date_creation',
        ]
        read_only_fields = [
            'caisse', 'montant_signe', 'posted', 'ecriture', 'date_creation']

    def validate_montant(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être strictement positif.")
        return value

    def validate_compte_contrepartie(self, value):
        return _meme_societe(self, value, 'Compte de contrepartie')


class ClotureCaisseSerializer(serializers.ModelSerializer):
    """Clôture de caisse : comptage physique à une date (FG124) — lecture seule.

    Les clôtures sont CALCULÉES par le service (action ``cloturer`` de la
    caisse) : le solde théorique et l'écart sont figés côté serveur, jamais
    saisis. Ce sérialiseur ne sert qu'à les restituer.
    """
    class Meta:
        model = ClotureCaisse
        fields = [
            'id', 'caisse', 'date_cloture', 'solde_theorique', 'solde_compte',
            'ecart', 'commentaire', 'cloturee_par', 'date_creation',
        ]
        read_only_fields = fields


# ── FG125 — Virements internes entre comptes de trésorerie ─────────────────

class VirementInterneSerializer(serializers.ModelSerializer):
    """Virement interne entre deux comptes de trésorerie (FG125).

    ``company`` posée côté serveur. ``compte_source``/``compte_destination``
    validés comme appartenant à la société et différents. ``posted``/``ecriture``
    en lecture seule (posés via l'action ``poster``).
    """
    source_libelle = serializers.CharField(
        source='compte_source.libelle', read_only=True)
    destination_libelle = serializers.CharField(
        source='compte_destination.libelle', read_only=True)

    class Meta:
        model = VirementInterne
        fields = [
            'id', 'compte_source', 'source_libelle', 'compte_destination',
            'destination_libelle', 'date_virement', 'montant', 'libelle',
            'reference', 'posted', 'ecriture', 'date_creation',
        ]
        read_only_fields = ['posted', 'ecriture', 'date_creation']

    def validate_compte_source(self, value):
        return _meme_societe(self, value, 'Compte source')

    def validate_compte_destination(self, value):
        return _meme_societe(self, value, 'Compte destination')

    def validate_montant(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être strictement positif.")
        return value

    def validate(self, attrs):
        src = attrs.get('compte_source')
        dst = attrs.get('compte_destination')
        if src is not None and dst is not None and src.id == dst.id:
            raise serializers.ValidationError(
                "Les comptes source et destination doivent être différents.")
        return attrs


# ── FG126 — Prévisionnel de trésorerie roulant 13 semaines ─────────────────

class LignePrevisionnelTresorerieSerializer(serializers.ModelSerializer):
    """Ligne prévue d'un prévisionnel de trésorerie (FG126).

    ``company`` posée côté serveur. ``montant`` signé (+ encaissement, −
    décaissement), non nul.
    """
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    recurrence_display = serializers.CharField(
        source='get_recurrence_display', read_only=True)

    class Meta:
        model = LignePrevisionnelTresorerie
        fields = [
            'id', 'libelle', 'categorie', 'categorie_display', 'date_prevue',
            'montant', 'recurrence', 'recurrence_display', 'commentaire',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_montant(self, value):
        if value is not None and value == 0:
            raise serializers.ValidationError(
                "Le montant d'une ligne prévue ne peut être nul.")
        return value


# ── FG127 / FG128 — Effets (chèques / traites) ─────────────────────────────

class EffetSerializer(serializers.ModelSerializer):
    """Effet à recevoir (FG127) ou à payer (FG128).

    ``company`` posée côté serveur ; l'effet naît en ``portefeuille``. Le
    statut et les frais de rejet évoluent par les actions de service
    (remise/encaissement/paiement/rejet), jamais par écriture directe du corps.
    """
    sens_display = serializers.CharField(
        source='get_sens_display', read_only=True)
    type_effet_display = serializers.CharField(
        source='get_type_effet_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Effet
        fields = [
            'id', 'sens', 'sens_display', 'type_effet', 'type_effet_display',
            'numero', 'montant', 'date_emission', 'date_echeance', 'banque',
            'tireur', 'statut', 'statut_display', 'tiers_type', 'tiers_id',
            'bordereau', 'frais_rejet', 'commentaire', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'bordereau', 'frais_rejet', 'date_creation']

    def validate_montant(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Le montant d'un effet doit être strictement positif.")
        return value

    def validate(self, attrs):
        emission = attrs.get('date_emission')
        echeance = attrs.get('date_echeance')
        if emission and echeance and echeance < emission:
            raise serializers.ValidationError(
                "L'échéance doit être postérieure ou égale à l'émission.")
        return attrs


# ── FG129 — Bordereau de remise en banque ──────────────────────────────────

class BordereauRemiseSerializer(serializers.ModelSerializer):
    """Bordereau de remise en banque d'effets à recevoir (FG129).

    ``company`` posée côté serveur. ``compte_tresorerie`` validé comme banque de
    la société. Les effets liés et le total sont gérés par le service ; le
    posting passe les effets en ``remis``.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    compte_libelle = serializers.CharField(
        source='compte_tresorerie.libelle', read_only=True)
    effets = EffetSerializer(many=True, read_only=True)

    class Meta:
        model = BordereauRemise
        fields = [
            'id', 'compte_tresorerie', 'compte_libelle', 'reference',
            'date_remise', 'statut', 'statut_display', 'total', 'posted',
            'ecriture', 'effets', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'total', 'posted', 'ecriture', 'effets', 'date_creation']

    def validate_compte_tresorerie(self, value):
        value = _meme_societe(self, value, 'Compte de trésorerie')
        if value is not None and value.type_compte != (
                CompteTresorerie.Type.BANQUE):
            raise serializers.ValidationError(
                "Un bordereau de remise se dépose sur un compte bancaire.")
        return value


# ── FG131 — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) ────

class RapprochementSerializer(serializers.ModelSerializer):
    """Rapprochement 3 voies d'un achat avant paiement (FG131).

    ``company`` posée côté serveur. ``bon_commande`` est un BCF (apps.stock) —
    sa validité-société est vérifiée par le service à l'évaluation. Les montants
    (commandé/reçu/facturé), l'écart et le statut sont calculés côté serveur (en
    lecture seule ici) ; seuls ``bon_commande``, ``tolerance`` et ``note`` sont
    saisissables. ``bon_a_payer`` indique si le paiement est autorisé.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    bon_commande_reference = serializers.CharField(
        source='bon_commande.reference', read_only=True)
    fournisseur_nom = serializers.CharField(
        source='bon_commande.fournisseur.nom', read_only=True)
    ecart_commande_recu = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    bon_a_payer = serializers.BooleanField(read_only=True)

    class Meta:
        model = Rapprochement
        fields = [
            'id', 'bon_commande', 'bon_commande_reference', 'fournisseur_nom',
            'statut', 'statut_display', 'tolerance', 'montant_commande',
            'montant_recu', 'montant_facture', 'ecart', 'ecart_commande_recu',
            'bon_a_payer', 'note', 'date_evaluation', 'valide_par',
            'date_validation', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'montant_commande', 'montant_recu', 'montant_facture',
            'ecart', 'date_evaluation', 'valide_par', 'date_validation',
            'date_creation',
        ]

    def validate_tolerance(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La tolérance doit être positive ou nulle.")
        return value
