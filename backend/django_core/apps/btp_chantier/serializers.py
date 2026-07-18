"""Sérialiseurs du vertical BTP/EPC (Groupe NTCON)."""
from django.utils import timezone
from rest_framework import serializers

from .models import (
    RFI, RFIReponse, ReserveChantier, ReserveChantierHistorique,
    AvenantChantier, DecompteGeneral, DiffusionPlan, JournalChantier,
    SignatureBtp, VisaDocument,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur (cross-
    tenant refusé — pattern ``gestion_projet.serializers._meme_societe``)."""
    request = serializer.context.get('request')
    if value is not None and request is not None and request.user.company_id:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


def _valider_localisation_plan(value):
    """Valide la forme du pin plan : ``document_ged_id`` + x/y ∈ [0, 1]."""
    if not isinstance(value, dict):
        raise serializers.ValidationError(
            'localisation_plan doit être un objet JSON.')
    doc_id = value.get('document_ged_id')
    if not doc_id or not isinstance(doc_id, int):
        raise serializers.ValidationError(
            "localisation_plan.document_ged_id est requis (id du document GED).")
    for axe in ('x', 'y'):
        coord = value.get(axe)
        if coord is None or not isinstance(coord, (int, float)):
            raise serializers.ValidationError(
                f'localisation_plan.{axe} est requis (coordonnée normalisée 0-1).')
        if not (0 <= coord <= 1):
            raise serializers.ValidationError(
                f'localisation_plan.{axe} doit être compris entre 0 et 1.')
    return value


class ReserveChantierHistoriqueSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = ReserveChantierHistorique
        fields = [
            'id', 'ancien_statut', 'nouveau_statut', 'motif',
            'auteur', 'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields


class SignatureBtpSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignatureBtp
        fields = [
            'id', 'contexte', 'signataire_nom', 'signataire', 'methode',
            'date_signature', 'ip_adresse', 'user_agent',
        ]
        read_only_fields = fields


class ReserveChantierSerializer(serializers.ModelSerializer):
    historique = ReserveChantierHistoriqueSerializer(many=True, read_only=True)

    class Meta:
        model = ReserveChantier
        fields = [
            'id', 'chantier', 'lot', 'localisation_plan', 'description',
            'gravite', 'statut', 'responsable_leve', 'date_limite',
            'created_by', 'created_at', 'updated_at',
            'date_levee', 'leve_par', 'motif_contestation', 'historique',
        ]
        read_only_fields = [
            'id', 'statut', 'created_by', 'created_at', 'updated_at',
            'date_levee', 'leve_par', 'motif_contestation', 'historique',
        ]

    def validate_localisation_plan(self, value):
        return _valider_localisation_plan(value)

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')

    def validate_responsable_leve(self, value):
        return _meme_societe(self, value, 'Responsable')


# ── NTCON3 — RFI ─────────────────────────────────────────────────────────────

class RFIReponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFIReponse
        fields = ['id', 'rfi', 'texte', 'auteur', 'date_creation']
        read_only_fields = ['id', 'rfi', 'auteur', 'date_creation']


class RFISerializer(serializers.ModelSerializer):
    reponses = RFIReponseSerializer(many=True, read_only=True)
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = RFI
        fields = [
            'id', 'chantier', 'numero', 'question', 'pose_par',
            'destinataire_texte', 'destinataire_user', 'delai_jours',
            'date_limite_reponse', 'statut', 'impact_cout',
            'impact_delai_jours', 'created_at', 'reponses', 'en_retard',
        ]
        read_only_fields = [
            'id', 'numero', 'pose_par', 'date_limite_reponse', 'statut',
            'created_at', 'reponses', 'en_retard',
        ]

    def get_en_retard(self, obj):
        return bool(
            obj.statut == RFI.Statut.OUVERT and obj.date_limite_reponse
            and obj.date_limite_reponse < timezone.localdate())

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')

    def validate_destinataire_user(self, value):
        return _meme_societe(self, value, 'Destinataire')


# ── NTCON5 — Visas de documents techniques ──────────────────────────────────

class VisaDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaDocument
        fields = [
            'id', 'chantier', 'document_ged_id', 'reference', 'type_visa',
            'statut', 'soumis_par', 'date_soumission', 'revu_par',
            'date_revue', 'observations', 'delai_revue_jours', 'date_limite',
            'nb_resoumissions', 'created_at',
        ]
        read_only_fields = [
            'id', 'reference', 'statut', 'soumis_par', 'date_soumission',
            'revu_par', 'date_revue', 'observations', 'date_limite',
            'nb_resoumissions', 'created_at',
        ]

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')


# ── NTCON6 — Journal de chantier ─────────────────────────────────────────────

class JournalChantierSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalChantier
        fields = [
            'id', 'chantier', 'date', 'redacteur', 'meteo',
            'effectif_interne', 'effectif_sous_traitant',
            'materiel_present', 'evenements', 'visiteurs', 'created_at',
        ]
        read_only_fields = ['id', 'redacteur', 'created_at']

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')


# ── NTCON7/NTCON8 — Avenant de chantier ─────────────────────────────────────

class AvenantChantierSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvenantChantier
        fields = [
            'id', 'chantier', 'avenant_contrat_id', 'reference',
            'description', 'montant_ht', 'impact_delai_jours',
            'impact_budget', 'lignes', 'statut', 'token_expires_at',
            'budget_projet_id', 'facture_id', 'motif_refus', 'cree_par',
            'approuve_par', 'date_approbation', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'statut', 'token_expires_at',
            'budget_projet_id', 'facture_id', 'motif_refus', 'cree_par',
            'approuve_par', 'date_approbation', 'created_at', 'updated_at',
        ]

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')


class AvenantChantierPublicSerializer(serializers.ModelSerializer):
    """NTCON8 — vue publique (lien tokenisé, sans authentification) : jamais
    de coût interne, jamais d'ID d'autres objets internes."""
    class Meta:
        model = AvenantChantier
        fields = [
            'reference', 'description', 'montant_ht', 'impact_delai_jours',
            'lignes', 'statut', 'token_expires_at',
        ]
        read_only_fields = fields


# ── NTCON9/NTCON10 — DGD (Décompte Général et Définitif) ───────────────────

class DecompteGeneralSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecompteGeneral
        fields = [
            'id', 'chantier', 'reference', 'montant_marche_initial_ht',
            'situations_incluses', 'total_avenants_ht',
            'total_situations_facturees_ht', 'retenue_garantie_id',
            'retenue_garantie_montant', 'solde_du_ht', 'statut',
            'motif_contestation', 'montant_conteste', 'date_notification',
            'date_finalisation', 'finalise_par', 'historique_deverrouillage',
            'cree_par', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'total_avenants_ht',
            'total_situations_facturees_ht', 'retenue_garantie_montant',
            'solde_du_ht', 'statut', 'motif_contestation',
            'montant_conteste', 'date_notification', 'date_finalisation',
            'finalise_par', 'historique_deverrouillage', 'cree_par',
            'created_at', 'updated_at',
        ]

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')


# ── NTCON12/NTCON13 — Diffusion contrôlée de plans ──────────────────────────

class DiffusionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiffusionPlan
        fields = [
            'id', 'chantier', 'document_ged_id', 'version_diffusee',
            'destinataires_internes', 'destinataires_externes',
            'partage_ged_id', 'date_diffusion', 'accuse_reception',
            'cree_par', 'created_at',
        ]
        read_only_fields = [
            'id', 'partage_ged_id', 'date_diffusion', 'accuse_reception',
            'cree_par', 'created_at',
        ]

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')
