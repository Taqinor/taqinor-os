"""Sérialiseurs de la Comptabilité générale.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import (
    AppelTelephonique, AvancementRevenu, BaremeIndemnite, BordereauRemise,
    Budget, BudgetLigne,
    Caisse, Campagne, CautionBancaire, CentreCout, CessionImmobilisation,
    EnvoiCampagne,
    ClotureCaisse, CodePromotion,
    CommissionPayoutLine, CommissionPayoutRun, CompteComptable,
    CompteTresorerie, ContratAvancement, DeclarationTVA,
    DemandeApprobationConfig, DotationAmortissement,
    ECatalogue, EcritureComptable, Effet, EntiteConsolidation, EtapeSequence,
    ExecutionEtapeSequence, InscriptionSequence,
    ListeDiffusion, AbonnementListe, SegmentMarketing,
    ExerciceComptable, FormulaireIntake,
    Immobilisation, IndemniteChantier, Journal, LigneEcriture,
    LignePrevisionnelTresorerie, LigneReleve, MessageWhatsAppEntrant,
    ModeleDevis, MouvementCaisse, NoteFrais, OuverturePartage, RapportNoteFrais,
    PaymentRun, PaymentRunLine, PeriodeComptable, PlafondNoteFrais,
    PlanAmortissement,
    PlanComptable, Provision, ProvisionCreance, Rapprochement, RapprochementBancaire,
    RelanceDevisAbandonne, RetenueGarantie, RetenueSource, SequenceRelance,
    SessionGuidedSelling, TimbreFiscal, TravauxEnCours,
    VirementInterne,
    DocumentProposition, SimulationPublique, SimulationFinancement,
    OffreFinancement, LigneIncitation, EcheancierPaiement, TranchePaiement,
    AppelOffre, BordereauPrix, LigneBordereau, CautionSoumission,
    DossierSoumission, PieceSoumission, EcheanceAO, ResultatAO,
    ComptePortailClient, AcceptationDevisPortail, PaiementFacturePortail,
    DocumentClientPortail, JalonChantierPortail, DemandeTicketPortail,
    Partenaire, SoumissionLeadPartenaire, CommissionPartenaire,
    TerritoireCommercial, EnqueteNPS, AvisClient,
    CompteFidelite, MouvementFidelite, RegleUpsell,
    AbonnementMonitoring,
    MappingCompte, CompteAuxiliaire, PieceJustificative,
    PisteAuditComptable,
    ModeleRapprochement,
    ObligationFiscale,
    FamilleTvaNonDeductible,
    Compensation, LigneCompensation,
    ApprobationEnvoiCampagne,
    Enquete, ReponseEnquete,
    EvenementMarketing, InscriptionEvenement,
    SupportOffline,
    DomaineEnvoi,
    TypeEvenement,
    BilletEvenement,
    QuestionEvenement,
    CommunicationEvenement,
    PostSocial,
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
            'centre_cout',
        ]

    def validate_compte(self, value):
        return _meme_societe(self, value, 'Compte')

    def validate_centre_cout(self, value):
        return _meme_societe(self, value, 'Centre de coût')


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
            # COMPTA40 — traçabilité du second regard (lecture seule).
            'valide_par', 'date_validation',
        ]
        read_only_fields = [
            'date_creation', 'source_type', 'source_id', 'total_debit',
            'total_credit', 'valide_par', 'date_validation',
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
            'statut_display', 'an_reporte', 'date_cloture',
            'coefficient_prorata_tva', 'date_creation',
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
            'date_mise_en_service', 'actif', 'date_creation',
            'piece_origine_facture_fournisseur_id',
            'piece_origine_ligne_facture_fournisseur_id',
        ]
        read_only_fields = [
            'montant_tva', 'cout_ttc', 'date_creation',
            'piece_origine_facture_fournisseur_id',
            'piece_origine_ligne_facture_fournisseur_id',
        ]

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
            'agios_escompte', 'interets_escompte', 'date_escompte',
            'ecriture_escompte_id', 'ecriture_apurement_escompte_id',
            'beneficiaire_endossement', 'date_endossement',
        ]
        read_only_fields = [
            'statut', 'bordereau', 'frais_rejet', 'date_creation',
            'agios_escompte', 'interets_escompte', 'date_escompte',
            'ecriture_escompte_id', 'ecriture_apurement_escompte_id',
            'beneficiaire_endossement', 'date_endossement',
        ]

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


# ── FG133 — Campagnes de règlement fournisseurs (payment run) ──────────────

class PaymentRunLineSerializer(serializers.ModelSerializer):
    """Ligne d'une campagne de règlement : une échéance fournisseur à payer.

    ``company``/``payment_run`` sont posés côté serveur. Le bénéficiaire et les
    coordonnées bancaires manquants sont complétés depuis le sélecteur de stock
    par le service à l'ajout.
    """
    class Meta:
        model = PaymentRunLine
        fields = [
            'id', 'tiers_type', 'tiers_id', 'beneficiaire', 'reference',
            'montant', 'date_echeance', 'rib', 'iban',
            'facture_fournisseur_id',
        ]
        read_only_fields = ['facture_fournisseur_id']

    def validate_montant(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Le montant d'une ligne de règlement doit être strictement "
                "positif.")
        return value


class PaymentRunSerializer(serializers.ModelSerializer):
    """Campagne de règlement fournisseurs (FG133).

    ``company`` posée côté serveur ; ``compte_tresorerie`` validé comme banque de
    la société. ``lignes`` est saisissable à la création (le service complète
    les bénéficiaires/coordonnées et recalcule le total) puis en lecture seule.
    Le statut, le total, le posting et l'écriture évoluent par les actions de
    service (figer/poster), jamais par écriture directe du corps.
    """
    mode_paiement_display = serializers.CharField(
        source='get_mode_paiement_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    compte_libelle = serializers.CharField(
        source='compte_tresorerie.libelle', read_only=True, default='')
    lignes = PaymentRunLineSerializer(many=True, required=False)

    class Meta:
        model = PaymentRun
        fields = [
            'id', 'reference', 'mode_paiement', 'mode_paiement_display',
            'compte_tresorerie', 'compte_libelle', 'date_paiement', 'statut',
            'statut_display', 'total', 'posted', 'ecriture', 'note', 'lignes',
            'date_creation',
        ]
        read_only_fields = [
            'statut', 'total', 'posted', 'ecriture', 'date_creation']

    def validate_compte_tresorerie(self, value):
        value = _meme_societe(self, value, 'Compte de trésorerie')
        if value is not None and value.type_compte != (
                CompteTresorerie.Type.BANQUE):
            raise serializers.ValidationError(
                "Le règlement par virement se débite d'un compte bancaire.")
        return value


class NoteFraisSerializer(serializers.ModelSerializer):
    """Note de frais employé (FG135).

    La création n'expose que les champs de saisie (employé, dépense,
    justificatif photo) ; ``company``/``reference``/statut et les écritures sont
    posés côté serveur. Le cycle (soumise/validée/rejetée/remboursée) évolue par
    les actions de service, jamais par écriture directe du corps.
    """
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    employe_nom = serializers.CharField(
        source='employe.get_full_name', read_only=True, default='')

    class Meta:
        model = NoteFrais
        fields = [
            'id', 'reference', 'employe', 'employe_nom', 'date_frais',
            'categorie', 'categorie_display', 'montant', 'motif',
            'justificatif', 'statut', 'statut_display', 'compte_charge',
            'valide_par', 'date_validation', 'ecriture_charge', 'motif_rejet',
            'mode_remboursement', 'compte_tresorerie', 'date_remboursement',
            'rembourse_par', 'ecriture_remboursement', 'date_creation',
            'hors_politique',
            'refacturable', 'taux_marge', 'client_refacturation_id',
            'chantier_refacturation', 'facture_refacturation_id',
        ]
        read_only_fields = [
            'reference', 'statut', 'valide_par', 'date_validation',
            'ecriture_charge', 'motif_rejet', 'compte_tresorerie',
            'date_remboursement', 'rembourse_par', 'ecriture_remboursement',
            'date_creation', 'hors_politique', 'facture_refacturation_id',
        ]

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_compte_charge(self, value):
        return _meme_societe(self, value, 'Compte de charge')

    def validate_montant(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Le montant d'une note de frais doit être strictement positif.")
        return value


# ── ZACC6 — Rapport de notes de frais (regroupement multi-lignes) ─────────

class RapportNoteFraisSerializer(serializers.ModelSerializer):
    """Rapport regroupant N notes de frais d'un employé (ZACC6).

    La création n'expose que ``employe``/``libelle`` ; ``company``/
    ``reference``/statut/écritures sont posés côté serveur. Le rattachement
    des notes se fait via l'action ``creer`` (corps ``note_frais_ids``), et le
    cycle (soumis/validé/remboursé) évolue par les actions de service."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    employe_nom = serializers.CharField(
        source='employe.get_full_name', read_only=True, default='')
    montant_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    notes_ids = serializers.PrimaryKeyRelatedField(
        source='notes', many=True, read_only=True)

    class Meta:
        model = RapportNoteFrais
        fields = [
            'id', 'reference', 'employe', 'employe_nom', 'libelle', 'statut',
            'statut_display', 'montant_total', 'notes_ids',
            'valide_par', 'date_validation', 'ecriture_charge',
            'mode_remboursement', 'compte_tresorerie', 'date_remboursement',
            'rembourse_par', 'ecriture_remboursement', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'statut', 'valide_par', 'date_validation',
            'ecriture_charge', 'compte_tresorerie', 'date_remboursement',
            'rembourse_par', 'ecriture_remboursement', 'date_creation',
        ]

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


# ── XACC27 — Plafonds de notes de frais par catégorie ──────────────────────

class PlafondNoteFraisSerializer(serializers.ModelSerializer):
    """Plafond par catégorie de note de frais (XACC27). ``company`` posée
    côté serveur."""
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)

    class Meta:
        model = PlafondNoteFrais
        fields = [
            'id', 'categorie', 'categorie_display', 'montant_max',
            'seuil_justificatif_obligatoire', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_montant_max(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le plafond ne peut pas être négatif.")
        return value


class BaremeIndemniteSerializer(serializers.ModelSerializer):
    """Barème d'indemnités km/per-diem d'une société (FG136).

    ``company`` est posée côté serveur (TenantMixin). Les tarifs ne peuvent pas
    être négatifs.
    """
    class Meta:
        model = BaremeIndemnite
        fields = [
            'id', 'libelle', 'taux_km', 'per_diem', 'defaut', 'actif',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_taux_km(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "L'indemnité kilométrique ne peut pas être négative.")
        return value

    def validate_per_diem(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le per-diem ne peut pas être négatif.")
        return value


class IndemniteChantierSerializer(serializers.ModelSerializer):
    """Indemnité kilométrique & per-diem chantier d'un employé (FG136).

    À la création on n'accepte que les champs de saisie (employé, barème, GPS
    départ/chantier, jours, aller-retour) ; la distance et les montants sont
    calculés AUTOMATIQUEMENT côté serveur (haversine × barème) et restent en
    lecture seule, comme ``company``/``reference``/statut et les écritures.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    employe_nom = serializers.CharField(
        source='employe.get_full_name', read_only=True, default='')
    bareme_libelle = serializers.CharField(
        source='bareme.libelle', read_only=True, default='')

    class Meta:
        model = IndemniteChantier
        fields = [
            'id', 'reference', 'employe', 'employe_nom', 'bareme',
            'bareme_libelle', 'date_deplacement', 'libelle_chantier',
            'depart_lat', 'depart_lng', 'site_lat', 'site_lng', 'aller_retour',
            'nombre_jours', 'distance_km', 'montant_km', 'montant_per_diem',
            'montant_total', 'statut', 'statut_display', 'compte_charge',
            'valide_par', 'date_validation', 'ecriture_charge', 'motif_rejet',
            'compte_tresorerie', 'date_remboursement', 'rembourse_par',
            'ecriture_remboursement', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'distance_km', 'montant_km', 'montant_per_diem',
            'montant_total', 'statut', 'compte_charge', 'valide_par',
            'date_validation', 'ecriture_charge', 'motif_rejet',
            'compte_tresorerie', 'date_remboursement', 'rembourse_par',
            'ecriture_remboursement', 'date_creation',
        ]
        extra_kwargs = {'bareme': {'required': False}}

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_bareme(self, value):
        return _meme_societe(self, value, 'Barème')


class DeclarationTVASerializer(serializers.ModelSerializer):
    """Préparation d'une déclaration de TVA sur une période (FG137).

    À la création on n'accepte que les champs de cadrage (période, régime,
    méthode, crédit antérieur, libellé) ; la TVA collectée/déductible, le montant
    à déclarer et le crédit reportable sont DÉRIVÉS du grand livre côté serveur et
    restent en lecture seule, comme ``company``/``reference``/statut.
    """
    regime_display = serializers.CharField(
        source='get_regime_display', read_only=True)
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = DeclarationTVA
        fields = [
            'id', 'reference', 'regime', 'regime_display', 'methode',
            'methode_display', 'date_debut', 'date_fin', 'credit_anterieur',
            'tva_collectee', 'tva_deductible', 'tva_a_declarer',
            'credit_reportable', 'statut', 'statut_display', 'libelle',
            'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'tva_collectee', 'tva_deductible', 'tva_a_declarer',
            'credit_reportable', 'statut', 'created_by', 'date_creation',
        ]


class ObligationFiscaleSerializer(serializers.ModelSerializer):
    """Échéance du calendrier fiscal (XACC9) — LECTURE SEULE (générée par le
    service, jamais créée à la main via l'API)."""
    type_display = serializers.CharField(
        source='get_type_obligation_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = ObligationFiscale
        fields = [
            'id', 'type_obligation', 'type_display', 'periode_debut',
            'periode_fin', 'date_limite', 'statut', 'statut_display',
            'libelle', 'source_type', 'source_id', 'rappel_envoye_le',
            'date_creation',
        ]
        read_only_fields = fields


class FamilleTvaNonDeductibleSerializer(serializers.ModelSerializer):
    """Famille de charge à TVA non déductible (XACC11, véhicules de
    tourisme…)."""

    class Meta:
        model = FamilleTvaNonDeductible
        fields = ['id', 'famille', 'libelle', 'actif', 'date_creation']
        read_only_fields = ['date_creation']


class RetenueSourceSerializer(serializers.ModelSerializer):
    """Retenue à la source (RAS) sur honoraires/prestations (FG139).

    À la création on accepte la saisie de la pièce (base, taux, type de
    prestation, prestataire/IF) ; le ``montant`` retenu est DÉRIVÉ côté serveur
    (base × taux %) et reste en lecture seule, comme
    ``company``/``reference``/statut/``created_by``. Le statut évolue par
    l'action de service (versée), jamais par écriture directe du corps.
    """
    type_prestation_display = serializers.CharField(
        source='get_type_prestation_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    net_a_payer = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = RetenueSource
        fields = [
            'id', 'reference', 'piece', 'date_piece', 'type_prestation',
            'type_prestation_display', 'tiers_type', 'tiers_id', 'tiers_nom',
            'identifiant_fiscal', 'base', 'taux', 'montant', 'net_a_payer',
            'statut', 'statut_display', 'libelle', 'created_by',
            'date_creation',
        ]
        read_only_fields = [
            'reference', 'montant', 'statut', 'created_by', 'date_creation',
        ]

    def validate_base(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La base imposable ne peut pas être négative.")
        return value

    def validate_taux(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                "Le taux de RAS doit être compris entre 0 et 100 %.")
        return value


class TimbreFiscalSerializer(serializers.ModelSerializer):
    """Droit de timbre sur un encaissement en espèces (FG144).

    À la création on accepte la saisie de l'encaissement (base, mode de règlement,
    taux/minimum optionnels, paiement d'origine, payeur) ; le ``montant`` du timbre
    est DÉRIVÉ côté serveur (max(base × taux %, minimum)) et reste en lecture seule,
    comme ``company`` / ``reference`` / ``statut`` / ``created_by``. Le statut évolue
    par l'action de service (versé), jamais par écriture directe du corps.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = TimbreFiscal
        fields = [
            'id', 'reference', 'date_encaissement', 'paiement_id',
            'facture_ref', 'mode_reglement', 'tiers_type', 'tiers_id',
            'tiers_nom', 'base', 'taux', 'minimum', 'montant', 'statut',
            'statut_display', 'libelle', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'montant', 'statut', 'created_by', 'date_creation',
        ]

    def validate_base(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant encaissé ne peut pas être négatif.")
        return value

    def validate_taux(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                "Le taux du droit de timbre doit être compris entre 0 et 100 %.")
        return value

    def validate_minimum(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le minimum de perception ne peut pas être négatif.")
        return value


class RetenueGarantieSerializer(serializers.ModelSerializer):
    """Retenue de garantie (RG / bonne fin) sur un marché (FG145).

    À la création on accepte la saisie du décompte (base, taux, marché/facture,
    maître d'ouvrage, dates) ; le ``montant`` retenu est DÉRIVÉ côté serveur
    (base × taux %) et reste en lecture seule, comme
    ``company`` / ``reference`` / ``statut`` / ``date_liberation`` /
    ``created_by``. Le statut évolue par l'action de service (libérer), jamais par
    écriture directe du corps.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = RetenueGarantie
        fields = [
            'id', 'reference', 'marche_ref', 'facture_id', 'facture_ref',
            'tiers_type', 'tiers_id', 'tiers_nom', 'base', 'taux', 'montant',
            'date_constitution', 'date_levee_prevue', 'statut', 'statut_display',
            'date_liberation', 'libelle', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'montant', 'statut', 'date_liberation', 'created_by',
            'date_creation',
        ]

    def validate_base(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La base du décompte ne peut pas être négative.")
        return value

    def validate_taux(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                "Le taux de RG doit être compris entre 0 et 100 %.")
        return value


class CautionBancaireSerializer(serializers.ModelSerializer):
    """Caution / garantie bancaire émise sur un marché (FG145).

    À la création on accepte la saisie de l'engagement (type, banque, montant,
    marché, bénéficiaire, dates) ; ``company`` / ``reference`` / ``statut`` /
    ``date_mainlevee`` / ``created_by`` restent en lecture seule. Le statut évolue
    par l'action de service (mainlevée/restitution), jamais par écriture directe
    du corps.
    """
    type_caution_display = serializers.CharField(
        source='get_type_caution_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = CautionBancaire
        fields = [
            'id', 'reference', 'type_caution', 'type_caution_display',
            'marche_ref', 'tiers_nom', 'banque', 'montant', 'date_emission',
            'date_echeance', 'statut', 'statut_display', 'date_mainlevee',
            'libelle', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'statut', 'date_mainlevee', 'created_by',
            'date_creation',
        ]

    def validate_montant(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant de la caution ne peut pas être négatif.")
        return value


# ── FG146 — Reconnaissance du revenu par avancement (% completion) ──────────

class ContratAvancementSerializer(serializers.ModelSerializer):
    """Contrat reconnu au pourcentage d'avancement (FG146).

    ``company`` / ``reference`` / ``statut`` / ``created_by`` sont posés côté
    serveur. Le revenu reconnu et le reste sont dérivés en lecture seule.
    """
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    revenu_reconnu = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ContratAvancement
        fields = [
            'id', 'reference', 'libelle', 'chantier_ref', 'marche_ref',
            'client_id', 'client_nom', 'methode', 'methode_display',
            'revenu_total', 'cout_total_estime', 'date_debut',
            'date_fin_prevue', 'statut', 'statut_display', 'revenu_reconnu',
            'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'statut', 'revenu_reconnu', 'created_by',
            'date_creation',
        ]

    def validate_revenu_total(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le revenu total ne peut pas être négatif.")
        return value


class AvancementRevenuSerializer(serializers.ModelSerializer):
    """Constat périodique d'avancement et de revenu reconnu (FG146).

    Le ``%``, le revenu cumulé/de la période et l'écriture OD sont DÉRIVÉS côté
    serveur (jamais imposés par le corps).
    """
    class Meta:
        model = AvancementRevenu
        fields = [
            'id', 'contrat', 'date_arrete', 'pourcentage',
            'cout_engage_cumule', 'revenu_cumule', 'revenu_periode',
            'ecriture_id', 'libelle', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'pourcentage', 'revenu_cumule', 'revenu_periode', 'ecriture_id',
            'created_by', 'date_creation',
        ]


# ── FG147 — Produits constatés d'avance & travaux en cours (WIP) ────────────

class TravauxEnCoursSerializer(serializers.ModelSerializer):
    """Régularisation de cut-off (PCA / WIP) — FG147.

    ``company`` / ``reference`` / ``statut`` / écritures sont posés côté
    serveur. Le montant est saisi ; le poste OD est dérivé par le service.
    """
    nature_display = serializers.CharField(
        source='get_nature_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = TravauxEnCours
        fields = [
            'id', 'reference', 'nature', 'nature_display', 'libelle',
            'chantier_ref', 'contrat_id', 'montant', 'date_arrete', 'statut',
            'statut_display', 'ecriture_id', 'ecriture_reprise_id',
            'date_reprise', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'statut', 'ecriture_id', 'ecriture_reprise_id',
            'date_reprise', 'created_by', 'date_creation',
        ]

    def validate_montant(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant régularisé ne peut pas être négatif.")
        return value


# ── FG148 — Campagnes de versement des commissions (payout run) ─────────────

class CommissionPayoutLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionPayoutLine
        fields = [
            'id', 'run', 'commercial_id', 'commercial_nom', 'base', 'taux',
            'montant', 'libelle',
        ]
        read_only_fields = ['run']

    def validate_montant(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant de la commission ne peut pas être négatif.")
        return value


class CommissionPayoutRunSerializer(serializers.ModelSerializer):
    """Campagne de versement des commissions (FG148).

    ``company`` / ``reference`` / ``statut`` / ``total`` / ``ecriture_id`` sont
    posés côté serveur. Le statut évolue par les actions (valider / poster).
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    lignes = CommissionPayoutLineSerializer(many=True, read_only=True)

    class Meta:
        model = CommissionPayoutRun
        fields = [
            'id', 'reference', 'libelle', 'periode', 'date_run', 'statut',
            'statut_display', 'total', 'ecriture_id', 'date_validation',
            'date_poste', 'lignes', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'statut', 'total', 'ecriture_id', 'date_validation',
            'date_poste', 'created_by', 'date_creation',
        ]


# ── FG149 — Budgets annuels & suivi budget-vs-réalisé ──────────────────────

class BudgetLigneSerializer(serializers.ModelSerializer):
    compte_numero = serializers.CharField(
        source='compte.numero', read_only=True)
    montant_annuel = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BudgetLigne
        fields = [
            'id', 'budget', 'compte', 'compte_numero', 'centre_cout',
            'libelle', 'm01', 'm02', 'm03', 'm04', 'm05', 'm06', 'm07', 'm08',
            'm09', 'm10', 'm11', 'm12', 'montant_annuel',
        ]
        read_only_fields = ['budget']

    def validate_compte(self, value):
        return _meme_societe(self, value, 'Compte')

    def validate_centre_cout(self, value):
        return _meme_societe(self, value, 'Centre de coût')


class BudgetSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    lignes = BudgetLigneSerializer(many=True, read_only=True)

    class Meta:
        model = Budget
        fields = [
            'id', 'annee', 'libelle', 'statut', 'statut_display', 'lignes',
            'created_by', 'date_creation',
        ]
        read_only_fields = ['statut', 'created_by', 'date_creation']


# ── FG150 — Comptabilité analytique / centres de coût ──────────────────────

class CentreCoutSerializer(serializers.ModelSerializer):
    axe_display = serializers.CharField(
        source='get_axe_display', read_only=True)

    class Meta:
        model = CentreCout
        fields = [
            'id', 'code', 'libelle', 'axe', 'axe_display', 'actif',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG152 — Provisions pour créances douteuses ─────────────────────────────

class ProvisionCreanceSerializer(serializers.ModelSerializer):
    """Provision pour créance douteuse (FG152).

    ``dotation`` est DÉRIVÉE côté serveur (base × taux %) ; ``company`` /
    ``reference`` / ``statut`` / écritures restent en lecture seule.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = ProvisionCreance
        fields = [
            'id', 'reference', 'tiers_type', 'tiers_id', 'tiers_nom', 'base',
            'taux', 'dotation', 'anciennete_jours', 'date_dotation', 'statut',
            'statut_display', 'ecriture_id', 'ecriture_reprise_id',
            'date_reprise', 'libelle', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'dotation', 'statut', 'ecriture_id',
            'ecriture_reprise_id', 'date_reprise', 'created_by',
            'date_creation',
        ]

    def validate_base(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La base de la provision ne peut pas être négative.")
        return value

    def validate_taux(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                "Le taux de provision doit être compris entre 0 et 100 %.")
        return value


# ── XACC26 — Provisions risques & charges / dépréciation stock / immo ─────

class ProvisionSerializer(serializers.ModelSerializer):
    """Provision générique risques/charges/stock/immo (XACC26).

    ``company`` / ``reference`` / ``montant_repris`` / écriture(s) restent en
    lecture seule (posés côté service).
    """
    nature_display = serializers.CharField(
        source='get_nature_display', read_only=True)
    solde = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Provision
        fields = [
            'id', 'reference', 'nature', 'nature_display', 'motif',
            'montant_dotation', 'montant_repris', 'solde',
            'date_echeance_revue', 'date_dotation', 'ecriture_dotation_id',
            'date_derniere_reprise', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'reference', 'montant_repris', 'ecriture_dotation_id',
            'date_derniere_reprise', 'created_by', 'date_creation',
        ]

    def validate_montant_dotation(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant de la dotation ne peut pas être négatif.")
        return value


# ── FG153 — Inter-sociétés / consolidation multi-entités ───────────────────

class EntiteConsolidationSerializer(serializers.ModelSerializer):
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)
    entite_nom = serializers.CharField(
        source='entite.nom', read_only=True)

    class Meta:
        model = EntiteConsolidation
        fields = [
            'id', 'entite', 'entite_nom', 'libelle', 'pourcentage_interet',
            'methode', 'methode_display', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_pourcentage_interet(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                "Le pourcentage d'intérêt doit être entre 0 et 100 %.")
        return value


# ── FG201 — Campagnes email & SMS ──────────────────────────────────────────

class CampagneSerializer(serializers.ModelSerializer):
    canal_display = serializers.CharField(
        source='get_canal_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # ZMKT2 — colonnes de performance dérivées (0 si division par zéro).
    taux_delivre_pct = serializers.SerializerMethodField()
    taux_ouverture_pct = serializers.SerializerMethodField()
    taux_clic_pct = serializers.SerializerMethodField()
    taux_desinscription_pct = serializers.SerializerMethodField()

    class Meta:
        model = Campagne
        fields = [
            'id', 'nom', 'canal', 'canal_display', 'objet', 'corps', 'segment',
            'listes', 'sms_sender_id', 'whatsapp_template', 'statut',
            'statut_display',
            'nb_destinataires', 'nb_envois', 'nb_ouvertures', 'nb_clics',
            'envoyee_le', 'date_creation',
            'planifiee_le', 'debit_max_par_heure', 'variantes_langue',
            'ab_test', 'ab_gagnant', 'ab_decide_le',
            'budget_mad', 'cout_reel_mad', 'lignes_cout',
            'parente', 'rattachements', 'est_modele',
            'taux_delivre_pct', 'taux_ouverture_pct', 'taux_clic_pct',
            'taux_desinscription_pct',
        ]
        read_only_fields = [
            'statut', 'nb_destinataires', 'nb_envois', 'nb_ouvertures',
            'nb_clics', 'envoyee_le', 'date_creation',
            'ab_gagnant', 'ab_decide_le',
        ]

    def _pct(self, numerateur, denominateur):
        if not denominateur:
            return 0.0
        return round(numerateur / denominateur * 100, 1)

    def get_taux_delivre_pct(self, obj):
        delivres = obj.envois.exclude(
            statut__in=['rebond']).count() if obj.pk else 0
        return self._pct(delivres, obj.nb_envois)

    def get_taux_ouverture_pct(self, obj):
        return self._pct(obj.nb_ouvertures, obj.nb_envois)

    def get_taux_clic_pct(self, obj):
        return self._pct(obj.nb_clics, obj.nb_envois)

    def get_taux_desinscription_pct(self, obj):
        if not obj.pk:
            return 0.0
        nb_desinscrits = obj.envois.filter(statut='desinscrit').count()
        return self._pct(nb_desinscrits, obj.nb_envois)

    def validate_listes(self, value):
        request = self.context.get('request')
        if request is not None:
            for liste in value:
                if liste.company_id != request.user.company_id:
                    raise serializers.ValidationError('Liste inconnue.')
        return value

    def validate_corps(self, value):
        from apps.compta.services import valider_variables_fusion
        try:
            valider_variables_fusion(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value


# ── XMKT35 — Posts réseaux sociaux (calendrier de contenu) ──────────────────

class PostSocialSerializer(serializers.ModelSerializer):
    reseau_display = serializers.CharField(
        source='get_reseau_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = PostSocial
        fields = [
            'id', 'reseau', 'reseau_display', 'texte', 'media_key',
            'date_planifiee', 'statut', 'statut_display', 'rappel_envoye',
            'publie_le', 'external_id', 'erreur', 'date_creation',
        ]
        read_only_fields = [
            'rappel_envoye', 'publie_le', 'external_id', 'erreur',
            'date_creation',
        ]


# ── XMKT2 — Journal d'envoi par destinataire ────────────────────────────────

class EnvoiCampagneSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = EnvoiCampagne
        fields = [
            'id', 'campagne', 'destinataire', 'contact_ref', 'statut',
            'statut_display', 'raison_smtp', 'envoye_le', 'ouvert_le',
            'clique_le', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'raison_smtp', 'envoye_le', 'ouvert_le', 'clique_le',
            'date_creation',
        ]


class ApprobationEnvoiCampagneSerializer(serializers.ModelSerializer):
    """XMKT23 — demande d'approbation d'un envoi de masse."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    demande_par_nom = serializers.CharField(
        source='demande_par.username', read_only=True, default='')
    decide_par_nom = serializers.CharField(
        source='decide_par.username', read_only=True, default='')

    class Meta:
        model = ApprobationEnvoiCampagne
        fields = [
            'id', 'campagne', 'nb_destinataires_demandes', 'statut',
            'statut_display', 'demande_par_nom', 'decide_par_nom',
            'motif_rejet', 'date_creation', 'date_decision',
        ]
        read_only_fields = [
            'campagne', 'nb_destinataires_demandes', 'statut',
            'date_creation', 'date_decision',
        ]


# ── XMKT5 — Listes de diffusion nommées + abonnements ───────────────────────

class AbonnementListeSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AbonnementListe
        fields = [
            'id', 'liste', 'destinataire', 'contact_ref', 'statut',
            'statut_display', 'date_creation', 'date_maj',
        ]
        read_only_fields = ['date_creation', 'date_maj']

    def validate_liste(self, value):
        return _meme_societe(self, value, 'liste')


class ListeDiffusionSerializer(serializers.ModelSerializer):
    nb_abonnes = serializers.SerializerMethodField()

    class Meta:
        model = ListeDiffusion
        fields = [
            'id', 'nom', 'description', 'nb_abonnes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_nb_abonnes(self, obj):
        return obj.abonnements.filter(statut='inscrit').count()


# ── XMKT6 — Segments dynamiques enregistrés et réutilisables ────────────────

class SegmentMarketingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SegmentMarketing
        fields = ['id', 'nom', 'regles', 'date_creation']
        read_only_fields = ['date_creation']

    def validate_regles(self, value):
        from apps.compta.services import valider_regles_segment
        try:
            valider_regles_segment(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value


# ── FG202 — Séquences de relance automatisées ──────────────────────────────

class EtapeSequenceSerializer(serializers.ModelSerializer):
    canal_display = serializers.CharField(
        source='get_canal_display', read_only=True)

    class Meta:
        model = EtapeSequence
        fields = [
            'id', 'sequence', 'ordre', 'delai_jours', 'canal', 'canal_display',
            'modele_message',
        ]

    def validate_sequence(self, value):
        return _meme_societe(self, value, 'séquence')


class SequenceRelanceSerializer(serializers.ModelSerializer):
    etapes = EtapeSequenceSerializer(many=True, read_only=True)

    class Meta:
        model = SequenceRelance
        fields = [
            'id', 'nom', 'stage_declencheur', 'actif', 'date_creation',
            'etapes',
        ]
        read_only_fields = ['date_creation']


# ── XMKT1 — Inscriptions & exécution réelle des séquences ──────────────────

class ExecutionEtapeSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutionEtapeSequence
        fields = [
            'id', 'inscription', 'etape', 'execute_le', 'canal', 'resultat',
            'erreur',
        ]
        read_only_fields = ['execute_le']


class InscriptionSequenceSerializer(serializers.ModelSerializer):
    executions = ExecutionEtapeSequenceSerializer(many=True, read_only=True)

    class Meta:
        model = InscriptionSequence
        fields = [
            'id', 'sequence', 'lead_id', 'lead_reference', 'etape_courante',
            'statut', 'motif_sortie', 'declenchee_le', 'sortie_le',
            'executions',
        ]
        read_only_fields = ['declenchee_le', 'sortie_le']

    def validate_sequence(self, value):
        return _meme_societe(self, value, 'séquence')


# ── FG203 — Récupération des devis abandonnés ──────────────────────────────

class RelanceDevisAbandonneSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelanceDevisAbandonne
        fields = [
            'id', 'devis_id', 'devis_reference', 'jours_sans_reponse',
            'canal', 'note', 'date_relance',
        ]
        read_only_fields = ['date_relance']


# ── FG205 — Tracking d'ouverture des ShareLink ─────────────────────────────

class OuverturePartageSerializer(serializers.ModelSerializer):
    cible_display = serializers.CharField(
        source='get_cible_display', read_only=True)

    class Meta:
        model = OuverturePartage
        fields = [
            'id', 'token', 'cible', 'cible_display', 'cible_reference',
            'nb_ouvertures', 'premier_vu_le', 'dernier_vu_le',
        ]
        read_only_fields = [
            'nb_ouvertures', 'premier_vu_le', 'dernier_vu_le',
        ]


# ── FG206 — Formulaires d'intake / landing pages ───────────────────────────

class FormulaireIntakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormulaireIntake
        fields = [
            'id', 'nom', 'slug', 'tag_prefill', 'type_installation', 'champs',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG207 — Messages WhatsApp entrants (lecture) ───────────────────────────

class MessageWhatsAppEntrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageWhatsAppEntrant
        fields = [
            'id', 'wa_message_id', 'expediteur', 'nom_profil', 'texte',
            'lead_id', 'traite', 'date_reception',
        ]
        read_only_fields = fields


# ── FG208 — Journal d'appels & click-to-call ───────────────────────────────

class AppelTelephoniqueSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(
        source='get_direction_display', read_only=True)
    issue_display = serializers.CharField(
        source='get_issue_display', read_only=True)
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True)

    class Meta:
        model = AppelTelephonique
        fields = [
            'id', 'auteur', 'auteur_nom', 'lead_id', 'numero', 'direction',
            'direction_display', 'issue', 'issue_display', 'duree_secondes',
            'note', 'a_rappeler_le', 'date_appel',
        ]
        read_only_fields = ['auteur', 'auteur_nom', 'date_appel']


# ── FG209 — Codes de promotion ─────────────────────────────────────────────

class CodePromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodePromotion
        fields = [
            'id', 'code', 'libelle', 'taux_remise', 'date_debut', 'date_fin',
            'actif', 'nb_utilisations', 'ca_genere', 'date_creation',
        ]
        read_only_fields = [
            'nb_utilisations', 'ca_genere', 'date_creation',
        ]

    def validate_taux_remise(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                'Le taux de remise doit être entre 0 et 100 %.')
        return value

    def validate(self, attrs):
        debut = attrs.get('date_debut')
        fin = attrs.get('date_fin')
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                'La date de fin doit être postérieure à la date de début.')
        return attrs


# ── FG210 — Modèles de devis ───────────────────────────────────────────────

class ModeleDevisSerializer(serializers.ModelSerializer):
    marche_display = serializers.CharField(
        source='get_marche_display', read_only=True)

    class Meta:
        model = ModeleDevis
        fields = [
            'id', 'nom', 'marche', 'marche_display', 'description',
            'lignes_type', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG211 — Sessions de configuration guidée ───────────────────────────────

class SessionGuidedSellingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionGuidedSelling
        fields = [
            'id', 'auteur', 'marche', 'reponses', 'composition', 'complet',
            'date_creation',
        ]
        read_only_fields = [
            'auteur', 'composition', 'complet', 'date_creation',
        ]


# ── FG213 — Demandes d'approbation de configuration ────────────────────────

class DemandeApprobationConfigSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    demandeur_nom = serializers.CharField(
        source='demandeur.username', read_only=True)
    decideur_nom = serializers.CharField(
        source='decideur.username', read_only=True)

    class Meta:
        model = DemandeApprobationConfig
        fields = [
            'id', 'devis_id', 'devis_reference', 'motif', 'statut',
            'statut_display', 'demandeur', 'demandeur_nom', 'decideur',
            'decideur_nom', 'commentaire_decision', 'date_creation',
            'date_decision',
        ]
        read_only_fields = [
            'statut', 'demandeur', 'demandeur_nom', 'decideur', 'decideur_nom',
            'commentaire_decision', 'date_creation', 'date_decision',
        ]


# ── FG214 — E-catalogue public tokenisé ────────────────────────────────────

class ECatalogueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ECatalogue
        fields = [
            'id', 'titre', 'token', 'produit_ids', 'actif', 'expire_le',
            'date_creation',
        ]
        read_only_fields = ['token', 'date_creation']


# ── FG215 — Documents de proposition ───────────────────────────────────────

class DocumentPropositionSerializer(serializers.ModelSerializer):
    type_document_display = serializers.CharField(
        source='get_type_document_display', read_only=True)

    class Meta:
        model = DocumentProposition
        fields = [
            'id', 'titre', 'type_document', 'type_document_display', 'contenu',
            'fichier', 'ordre', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG216 — Simulations publiques ──────────────────────────────────────────

class SimulationPubliqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationPublique
        fields = [
            'id', 'nom_prospect', 'telephone', 'email', 'puissance_kwc',
            'facture_mensuelle', 'economie_annuelle', 'parametres',
            'lead_cree', 'lead_id', 'date_creation',
        ]
        read_only_fields = ['lead_cree', 'lead_id', 'date_creation']


# ── FG217 — Simulation de financement ──────────────────────────────────────

class SimulationFinancementSerializer(serializers.ModelSerializer):
    type_financement_display = serializers.CharField(
        source='get_type_financement_display', read_only=True)

    class Meta:
        model = SimulationFinancement
        fields = [
            'id', 'devis_id', 'devis_reference', 'type_financement',
            'type_financement_display', 'montant_finance', 'duree_mois',
            'taux_annuel', 'mensualite', 'cout_total_credit', 'date_creation',
        ]
        read_only_fields = ['mensualite', 'cout_total_credit', 'date_creation']


# ── FG218 — Offres de financement ──────────────────────────────────────────

class OffreFinancementSerializer(serializers.ModelSerializer):
    class Meta:
        model = OffreFinancement
        fields = [
            'id', 'partenaire', 'libelle', 'taux_annuel', 'duree_min_mois',
            'duree_max_mois', 'montant_min', 'montant_max', 'apport_min_pct',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG219 — Lignes d'incitation ────────────────────────────────────────────

class LigneIncitationSerializer(serializers.ModelSerializer):
    programme_display = serializers.CharField(
        source='get_programme_display', read_only=True)
    cout_net = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneIncitation
        fields = [
            'id', 'devis_id', 'devis_reference', 'programme',
            'programme_display', 'libelle', 'montant_aide', 'cout_brut',
            'cout_net', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG220 — Échéanciers et tranches de paiement ────────────────────────────

class TranchePaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranchePaiement
        fields = [
            'id', 'echeancier', 'numero', 'montant', 'date_echeance',
            'montant_regle', 'date_reglement', 'paye',
        ]


class EcheancierPaiementSerializer(serializers.ModelSerializer):
    tranches = TranchePaiementSerializer(many=True, read_only=True)
    montant_regle = serializers.SerializerMethodField()
    reste_a_payer = serializers.SerializerMethodField()

    class Meta:
        model = EcheancierPaiement
        fields = [
            'id', 'facture_id', 'facture_reference', 'montant_total', 'actif',
            'tranches', 'montant_regle', 'reste_a_payer', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_montant_regle(self, obj):
        total = Decimal('0.00')
        for tranche in obj.tranches.all():
            total += tranche.montant_regle or Decimal('0.00')
        return total

    def get_reste_a_payer(self, obj):
        return (obj.montant_total or Decimal('0.00')) - self.get_montant_regle(
            obj)


# ── FG222 — Appels d'offres ────────────────────────────────────────────────

class AppelOffreSerializer(serializers.ModelSerializer):
    type_marche_display = serializers.CharField(
        source='get_type_marche_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AppelOffre
        fields = [
            'id', 'reference', 'objet', 'acheteur', 'type_marche',
            'type_marche_display', 'lot', 'date_limite', 'montant_estime',
            'caution_provisoire', 'statut', 'statut_display', 'lead_id',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG223 — Bordereaux des prix (BOQ) ──────────────────────────────────────

class LigneBordereauSerializer(serializers.ModelSerializer):
    montant_ht = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = LigneBordereau
        fields = [
            'id', 'bordereau', 'numero', 'designation', 'unite', 'quantite',
            'prix_unitaire', 'montant_ht',
        ]


class BordereauPrixSerializer(serializers.ModelSerializer):
    lignes = LigneBordereauSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    appel_offre_reference = serializers.CharField(
        source='appel_offre.reference', read_only=True)

    class Meta:
        model = BordereauPrix
        fields = [
            'id', 'appel_offre', 'appel_offre_reference', 'intitule',
            'lignes', 'total_ht', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG224 — Cautions de soumission ─────────────────────────────────────────

class CautionSoumissionSerializer(serializers.ModelSerializer):
    type_caution_display = serializers.CharField(
        source='get_type_caution_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = CautionSoumission
        fields = [
            'id', 'appel_offre', 'type_caution', 'type_caution_display',
            'montant', 'banque', 'date_emission', 'date_echeance',
            'date_restitution', 'statut', 'statut_display', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG225 — Dossiers et pièces de soumission ───────────────────────────────

class PieceSoumissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceSoumission
        fields = [
            'id', 'dossier', 'libelle', 'obligatoire', 'fournie', 'fichier',
            'date_depot',
        ]


class DossierSoumissionSerializer(serializers.ModelSerializer):
    pieces = PieceSoumissionSerializer(many=True, read_only=True)
    complet = serializers.BooleanField(read_only=True)
    appel_offre_reference = serializers.CharField(
        source='appel_offre.reference', read_only=True)

    class Meta:
        model = DossierSoumission
        fields = [
            'id', 'appel_offre', 'appel_offre_reference', 'pieces', 'complet',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG226 — Échéances d'AO ─────────────────────────────────────────────────

class EcheanceAOSerializer(serializers.ModelSerializer):
    type_echeance_display = serializers.CharField(
        source='get_type_echeance_display', read_only=True)

    class Meta:
        model = EcheanceAO
        fields = [
            'id', 'appel_offre', 'type_echeance', 'type_echeance_display',
            'libelle', 'date_echeance', 'rappel_jours', 'traitee',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG227 — Résultats d'AO ─────────────────────────────────────────────────

class ResultatAOSerializer(serializers.ModelSerializer):
    issue_display = serializers.CharField(
        source='get_issue_display', read_only=True)
    ecart_prix = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, allow_null=True)
    appel_offre_reference = serializers.CharField(
        source='appel_offre.reference', read_only=True)

    class Meta:
        model = ResultatAO
        fields = [
            'id', 'appel_offre', 'appel_offre_reference', 'issue',
            'issue_display', 'attributaire', 'notre_prix', 'prix_gagnant',
            'ecart_prix', 'motif', 'date_resultat', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG228 — Comptes portail client ─────────────────────────────────────────

class ComptePortailClientSerializer(serializers.ModelSerializer):
    # DC32 — l'email est lu depuis le client (source unique), jamais stocké.
    email = serializers.EmailField(source='client.email', read_only=True)

    class Meta:
        model = ComptePortailClient
        fields = [
            'id', 'client', 'email', 'token_acces', 'actif',
            'derniere_connexion', 'date_creation',
        ]
        read_only_fields = [
            'token_acces', 'derniere_connexion', 'date_creation',
        ]


class AcceptationDevisPortailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcceptationDevisPortail
        fields = [
            'id', 'devis_id', 'option_choisie', 'nom_signataire',
            'signature_ip', 'accepte', 'signe_le', 'date_creation',
        ]
        read_only_fields = [
            'signature_ip', 'accepte', 'signe_le', 'date_creation',
        ]


class PaiementFacturePortailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaiementFacturePortail
        fields = [
            'id', 'facture_id', 'montant', 'methode', 'statut', 'reference',
            'paye_le', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'reference', 'paye_le', 'date_creation',
        ]


class DocumentClientPortailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentClientPortail
        fields = [
            'id', 'client_id', 'lead_id', 'type_document', 'libelle',
            'fichier', 'traite', 'date_depot',
        ]
        read_only_fields = ['traite', 'date_depot']


class JalonChantierPortailSerializer(serializers.ModelSerializer):
    class Meta:
        model = JalonChantierPortail
        fields = [
            'id', 'chantier_id', 'libelle', 'ordre', 'atteint', 'date_jalon',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class DemandeTicketPortailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandeTicketPortail
        fields = [
            'id', 'client_id', 'chantier_id', 'sujet', 'description',
            'statut', 'ticket_id', 'date_creation',
        ]
        read_only_fields = ['statut', 'ticket_id', 'date_creation']


class PartenaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partenaire
        fields = [
            'id', 'nom', 'type_partenaire', 'email', 'telephone',
            'taux_commission', 'token_acces', 'actif',
            'statut_onboarding', 'numero_agrement', 'zone', 'date_activation',
            'date_creation',
        ]
        read_only_fields = ['token_acces', 'date_activation', 'date_creation']


class SoumissionLeadPartenaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoumissionLeadPartenaire
        fields = [
            'id', 'partenaire', 'nom_prospect', 'telephone_prospect',
            'email_prospect', 'ville', 'note', 'statut', 'lead_id',
            'date_soumission',
        ]
        read_only_fields = ['statut', 'lead_id', 'date_soumission']

    def validate_partenaire(self, value):
        return _meme_societe(self, value, 'Partenaire')


class CommissionPartenaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionPartenaire
        fields = [
            'id', 'partenaire', 'devis_id', 'lead_id', 'base_ht', 'taux',
            'montant', 'statut', 'paye_le', 'date_creation',
        ]
        read_only_fields = ['montant', 'paye_le', 'date_creation']

    def validate_partenaire(self, value):
        return _meme_societe(self, value, 'Partenaire')


class TerritoireCommercialSerializer(serializers.ModelSerializer):
    class Meta:
        model = TerritoireCommercial
        fields = [
            'id', 'nom', 'villes', 'owner_user_id', 'priorite', 'actif',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class EnqueteNPSSerializer(serializers.ModelSerializer):
    categorie = serializers.CharField(read_only=True)

    class Meta:
        model = EnqueteNPS
        fields = [
            'id', 'client_id', 'chantier_id', 'score', 'commentaire',
            'statut', 'categorie', 'envoi_reel', 'envoyee_le', 'repondue_le',
        ]
        read_only_fields = [
            'statut', 'categorie', 'envoi_reel', 'envoyee_le', 'repondue_le',
        ]


class AvisClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvisClient
        fields = [
            'id', 'client_id', 'note', 'temoignage', 'statut',
            'google_review_url', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'google_review_url', 'date_creation',
        ]


class CompteFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompteFidelite
        fields = [
            'id', 'client_id', 'points', 'palier', 'date_creation',
        ]
        read_only_fields = ['points', 'palier', 'date_creation']


class MouvementFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MouvementFidelite
        fields = [
            'id', 'compte', 'points', 'motif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_compte(self, value):
        return _meme_societe(self, value, 'Compte de fidélité')


class RegleUpsellSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegleUpsell
        fields = [
            'id', 'declencheur', 'produit_suggere', 'message', 'priorite',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class AbonnementMonitoringSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbonnementMonitoring
        fields = [
            'id', 'client_id', 'installation_id', 'periodicite', 'montant',
            'statut', 'date_debut', 'prochaine_echeance',
            'derniere_facturation', 'motif_resiliation', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'date_debut', 'prochaine_echeance',
            'derniere_facturation', 'motif_resiliation', 'date_creation',
        ]


# ── COMPTA2 — Mapping document → compte ────────────────────────────────────

class MappingCompteSerializer(serializers.ModelSerializer):
    type_clef_display = serializers.CharField(
        source='get_type_clef_display', read_only=True)
    compte_numero = serializers.CharField(
        source='compte.numero', read_only=True)

    class Meta:
        model = MappingCompte
        fields = [
            'id', 'type_clef', 'type_clef_display', 'clef', 'compte',
            'compte_numero', 'libelle', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_compte(self, value):
        return _meme_societe(self, value, 'Compte')


class ModeleRapprochementSerializer(serializers.ModelSerializer):
    """Règle de contrepartie automatique (XACC4)."""
    compte_contrepartie_numero = serializers.CharField(
        source='compte_contrepartie.numero', read_only=True)

    class Meta:
        model = ModeleRapprochement
        fields = [
            'id', 'libelle', 'type_motif', 'motif', 'compte_contrepartie',
            'compte_contrepartie_numero', 'taux_tva', 'montant_fixe', 'auto',
            'actif', 'priorite', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_compte_contrepartie(self, value):
        return _meme_societe(self, value, 'Compte de contrepartie')


# ── COMPTA3 — Comptes auxiliaires tiers ────────────────────────────────────

class CompteAuxiliaireSerializer(serializers.ModelSerializer):
    type_tiers_display = serializers.CharField(
        source='get_type_tiers_display', read_only=True)
    compte_collectif_numero = serializers.CharField(
        source='compte_collectif.numero', read_only=True)

    class Meta:
        model = CompteAuxiliaire
        fields = [
            'id', 'compte_collectif', 'compte_collectif_numero', 'type_tiers',
            'type_tiers_display', 'tiers_id', 'code', 'actif', 'date_creation',
        ]
        read_only_fields = ['code', 'date_creation']

    def validate_compte_collectif(self, value):
        return _meme_societe(self, value, 'Compte collectif')


# ── COMPTA10 — Pièces justificatives sur écriture ──────────────────────────

class PieceJustificativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceJustificative
        fields = [
            'id', 'ecriture', 'libelle', 'fichier', 'ajoute_par',
            'date_creation',
        ]
        read_only_fields = ['ajoute_par', 'date_creation']

    def validate_ecriture(self, value):
        return _meme_societe(self, value, 'Écriture')


class PisteAuditComptableSerializer(serializers.ModelSerializer):
    """Maillon de piste d'audit hash-chaînée (COMPTA39) — lecture seule."""
    ecriture_reference = serializers.CharField(
        source='ecriture.reference', read_only=True)

    class Meta:
        model = PisteAuditComptable
        fields = [
            'id', 'ecriture', 'ecriture_reference', 'sequence',
            'empreinte_contenu', 'hash_precedent', 'hash', 'date_creation',
        ]
        read_only_fields = fields


class LigneCompensationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneCompensation
        fields = [
            'id', 'type_facture', 'facture_id', 'reference_facture',
            'montant_impute',
        ]
        read_only_fields = fields


class CompensationSerializer(serializers.ModelSerializer):
    """XFAC14 — Compensation AR/AP (netting). Lecture seule : la création
    passe par ``services.creer_compensation`` (garde-fous de sur-
    compensation), jamais un ``.create()`` direct du serializer."""
    lignes = LigneCompensationSerializer(many=True, read_only=True)

    class Meta:
        model = Compensation
        fields = [
            'id', 'reference', 'client_id', 'client_nom', 'fournisseur_id',
            'fournisseur_nom', 'montant_compense', 'statut', 'ecriture_id',
            'lignes', 'date_creation', 'date_validation',
        ]
        read_only_fields = fields


class EnqueteSerializer(serializers.ModelSerializer):
    """XMKT27 — Enquête configurable (constructeur avec logique
    conditionnelle)."""
    class Meta:
        model = Enquete
        fields = [
            'id', 'titre', 'questions', 'token', 'actif', 'date_creation',
            'mode_pagination', 'barre_progression', 'bouton_retour',
            'limite_temps_minutes', 'ordre_aleatoire',
            'mode_scoring', 'score_requis_pct', 'est_certification',
            'mode_acces', 'connexion_requise', 'tentatives_max',
            'description_accueil', 'message_fin',
        ]
        read_only_fields = ['token', 'date_creation']

    def validate_questions(self, value):
        from . import services
        try:
            return services.valider_questions_enquete(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))


class ReponseEnqueteSerializer(serializers.ModelSerializer):
    """XMKT27 — soumission (lecture seule côté admin — la création publique
    passe par ``enquete_soumettre``)."""
    class Meta:
        model = ReponseEnquete
        fields = ['id', 'enquete', 'contact_ref', 'reponses', 'date_creation']
        read_only_fields = fields


class EvenementMarketingSerializer(serializers.ModelSerializer):
    """XMKT28 — événement marketing léger (salon/porte ouverte/webinaire)."""
    type_display = serializers.CharField(
        source='get_type_evenement_display', read_only=True)
    nb_inscrits = serializers.IntegerField(
        source='inscriptions.count', read_only=True)

    class Meta:
        model = EvenementMarketing
        fields = [
            'id', 'nom', 'type_evenement', 'type_display', 'date_debut',
            'date_fin', 'lieu', 'capacite', 'nb_inscrits', 'date_creation',
            'etape', 'type_modele',
        ]
        read_only_fields = ['date_creation']


class TypeEvenementSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeEvenement
        fields = [
            'id', 'nom', 'type_evenement_defaut', 'config_defaut',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class BilletEvenementSerializer(serializers.ModelSerializer):
    places_restantes = serializers.IntegerField(read_only=True)
    nb_inscrits = serializers.IntegerField(
        source='inscriptions.count', read_only=True)

    class Meta:
        model = BilletEvenement
        fields = [
            'id', 'evenement', 'libelle', 'prix_ttc_mad',
            'date_debut_vente', 'date_fin_vente', 'quota',
            'places_restantes', 'nb_inscrits',
        ]


class InscriptionEvenementSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = InscriptionEvenement
        fields = [
            'id', 'evenement', 'nom', 'email', 'telephone', 'statut',
            'statut_display', 'qr_token', 'lead_id', 'date_creation',
            'date_pointage', 'billet', 'reponses_questions',
        ]
        read_only_fields = [
            'qr_token', 'lead_id', 'date_creation', 'date_pointage']


class QuestionEvenementSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionEvenement
        fields = [
            'id', 'evenement', 'libelle', 'type_question', 'obligatoire',
            'portee',
        ]


class CommunicationEvenementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationEvenement
        fields = [
            'id', 'evenement', 'canal', 'gabarit', 'intervalle',
            'unite_intervalle', 'envoyee_le',
        ]
        read_only_fields = ['envoyee_le']


class SupportOfflineSerializer(serializers.ModelSerializer):
    nb_scans = serializers.IntegerField(
        source='lien_tracke.nb_clics', read_only=True, default=0)

    class Meta:
        model = SupportOffline
        fields = ['id', 'nom', 'url_cible', 'nb_scans', 'date_creation']
        # url_cible est writable-on-create : perform_create le lit depuis
        # validated_data et re-dérive l'URL taguée UTM côté serveur via
        # services.creer_support_offline. Le laisser read-only le retirait de
        # validated_data → url_cible=None → 500 sur toute création par l'API.
        read_only_fields = ['nb_scans', 'date_creation']


class DomaineEnvoiSerializer(serializers.ModelSerializer):
    authentifie = serializers.BooleanField(read_only=True)

    class Meta:
        model = DomaineEnvoi
        fields = [
            'id', 'domaine', 'spf_verifie', 'dkim_verifie', 'dmarc_verifie',
            'authentifie', 'derniere_verification_le',
        ]
        read_only_fields = [
            'spf_verifie', 'dkim_verifie', 'dmarc_verifie',
            'derniere_verification_le',
        ]
