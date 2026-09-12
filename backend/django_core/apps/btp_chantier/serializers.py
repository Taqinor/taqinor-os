"""Sérialiseurs du vertical BTP/EPC (Groupe NTCON)."""
import re

from django.utils import timezone
from rest_framework import serializers

from .models import (
    RFI, RFIReponse, ReserveChantier, ReserveChantierHistorique,
    AvenantChantier, DecompteGeneral, DiffusionPlan, JournalChantier,
    AbonnementRapportPhoto, Lot, LotChecklistItem, ParametresBtpChantier,
    PPSPSChantier, PPSPSSignature, SignatureBtp, VisaDocument,
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
            # NTCON27 — état d'archivage, posé UNIQUEMENT par le balayage
            # planifié (lecture seule côté API).
            'archivee', 'archivee_le',
        ]
        read_only_fields = [
            'id', 'statut', 'created_by', 'created_at', 'updated_at',
            'date_levee', 'leve_par', 'motif_contestation', 'historique',
            'archivee', 'archivee_le',
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

    def validate_situations_incluses(self, value):
        # AUD310 — ``situations_incluses`` (IDs ``gestion_projet.
        # SituationTravaux``) était écrivable sans aucune vérification
        # société : un ID (devinable) d'une autre société s'agrégeait dans
        # les totaux du DGD, document contractuel de clôture de chantier.
        # Même patron que ``validate_chantier``/``_meme_societe``.
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'situations_incluses doit être une liste d\'identifiants.')
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None or not value:
            return value
        from . import selectors
        hors_societe = selectors.situations_incluses_hors_societe(
            value, company)
        if hors_societe:
            raise serializers.ValidationError(
                'Situation(s) inconnue(s) ou appartenant à une autre '
                f'société : {hors_societe}.')
        return value


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


# ── NTCON14 — Lots (planning TCE multi-lots) ────────────────────────────────

_HEX_COULEUR = re.compile(r'^#[0-9A-Fa-f]{6}$')


class LotSerializer(serializers.ModelSerializer):
    """NTCON14 — un lot du planning tous-corps-d'état.

    Les erreurs NOMMENT le champ fautif (règle fondateur « erreurs → le champ
    fautif ») : incohérence de dates → ``date_fin_prevue``, entreprise
    manquante → ``sous_traitant``, couleur invalide → ``couleur``.
    """
    taches = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.nom', read_only=True, default='')

    class Meta:
        model = Lot
        fields = [
            'id', 'chantier', 'nom', 'ordre', 'couleur', 'interne',
            'sous_traitant', 'sous_traitant_nom', 'date_debut_prevue',
            'date_fin_prevue', 'date_fin_reelle', 'jalon_contractuel',
            'montant_ht', 'taux_penalite_retard_pmil', 'plafond_penalite_pct',
            'statut', 'taches', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'sous_traitant_nom', 'taches', 'created_at', 'updated_at',
        ]

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')

    def validate_sous_traitant(self, value):
        return _meme_societe(self, value, 'Sous-traitant')

    def validate_couleur(self, value):
        if value and not _HEX_COULEUR.match(value):
            raise serializers.ValidationError(
                'Couleur invalide : attendu un code hexadécimal #RRGGBB '
                '(exemple : #2563EB).')
        return value

    def _valeur(self, attrs, champ):
        """Valeur effective d'un champ (PATCH partiel inclus)."""
        if champ in attrs:
            return attrs[champ]
        return getattr(self.instance, champ, None)

    def validate(self, attrs):
        debut = self._valeur(attrs, 'date_debut_prevue')
        fin = self._valeur(attrs, 'date_fin_prevue')
        if debut and fin and fin < debut:
            raise serializers.ValidationError({
                'date_fin_prevue': (
                    'La fin prévue ne peut pas précéder le début prévu '
                    f'({debut}).'),
            })
        interne = self._valeur(attrs, 'interne')
        sous_traitant = self._valeur(attrs, 'sous_traitant')
        if interne is False and sous_traitant is None:
            raise serializers.ValidationError({
                'sous_traitant': (
                    "Lot non exécuté en interne : l'entreprise "
                    '(sous-traitant) est obligatoire.'),
            })
        if interne and sous_traitant is not None:
            raise serializers.ValidationError({
                'interne': (
                    'Un lot confié à un sous-traitant ne peut pas être marqué '
                    '« exécuté en interne » — décochez la case.'),
            })
        return attrs


# ── NTCON25 — Réglages BTP par société ─────────────────────────────────────

class ParametresBtpChantierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresBtpChantier
        fields = [
            'id', 'delai_reponse_rfi_defaut_jours',
            'delai_revue_visa_defaut_jours', 'guard_ppsps_bloquant',
            'guard_checklist_lot_bloquant', 'lots_types_defaut',
            'taux_penalite_retard_defaut_pmil',
            # NTCON27 — ancienneté d'archivage des réserves levées (mois).
            'delai_archivage_reserves_levees_mois', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate_lots_types_defaut(self, value):
        """Liste de noms de lots — l'erreur NOMME l'entrée fautive."""
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'lots_types_defaut doit être une liste de noms de lots.')
        for nom in value:
            if not isinstance(nom, str) or not nom.strip():
                raise serializers.ValidationError(
                    f'Nom de lot invalide : « {nom} ».')
        return [nom.strip() for nom in value]

    def validate_taux_penalite_retard_defaut_pmil(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le taux de pénalité ne peut pas être négatif.')
        return value


# ── NTCON19 — Checklist de réception de lot ────────────────────────────────

class LotChecklistItemSerializer(serializers.ModelSerializer):
    fait_par_nom = serializers.CharField(
        source='fait_par.username', read_only=True, default='')

    class Meta:
        model = LotChecklistItem
        fields = [
            'id', 'cle', 'libelle', 'ordre', 'obligatoire', 'fait',
            'fait_par', 'fait_par_nom', 'fait_le',
        ]
        read_only_fields = fields


# ── NTCON16 — PPSPS de chantier + signatures sous-traitant ─────────────────

class PPSPSSignatureSerializer(serializers.ModelSerializer):
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.nom', read_only=True, default='')

    class Meta:
        model = PPSPSSignature
        fields = [
            'id', 'sous_traitant', 'sous_traitant_nom', 'signataire_nom',
            'methode', 'date_signature',
        ]
        read_only_fields = fields

    def validate_sous_traitant(self, value):
        """Défense en profondeur : ce sérialiseur est entièrement en LECTURE
        (``read_only_fields = fields`` — la signature est posée par
        ``services.signer_ppsps``), mais la garde même-société est déclarée
        explicitement pour qu'un futur passage en écriture ne puisse JAMAIS
        accepter un sous-traitant d'une autre société (``check_fk_scoping``)."""
        return _meme_societe(self, value, 'Sous-traitant')


class PPSPSChantierSerializer(serializers.ModelSerializer):
    signatures = PPSPSSignatureSerializer(many=True, read_only=True)
    est_valide = serializers.BooleanField(read_only=True)

    class Meta:
        model = PPSPSChantier
        fields = [
            'id', 'chantier', 'titre', 'document_ged_id', 'date_validation',
            'valide_par', 'lots_couverts', 'signatures', 'est_valide',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'date_validation', 'valide_par', 'signatures', 'est_valide',
            'created_at', 'updated_at',
        ]

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')

    def validate_lots_couverts(self, value):
        """Les lots couverts appartiennent à la société de l'utilisateur —
        l'erreur NOMME le champ fautif (``lots_couverts``)."""
        request = self.context.get('request')
        company_id = getattr(
            getattr(request, 'user', None), 'company_id', None)
        for lot in value or []:
            if company_id and lot.company_id != company_id:
                raise serializers.ValidationError('Lot inconnu.')
        return value

    def validate(self, attrs):
        chantier = attrs.get('chantier') or getattr(
            self.instance, 'chantier', None)
        lots = attrs.get('lots_couverts')
        if chantier is not None and lots:
            etrangers = [
                lot.nom for lot in lots if lot.chantier_id != chantier.pk]
            if etrangers:
                raise serializers.ValidationError({
                    'lots_couverts': (
                        'Ces lots ne sont pas ceux de ce chantier : '
                        f'{", ".join(etrangers)}.'),
                })
        return attrs


# ── NTCON18 — Abonnement au photo-rapport hebdomadaire ─────────────────────

class AbonnementRapportPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbonnementRapportPhoto
        fields = [
            'id', 'chantier', 'actif', 'destinataires', 'dernier_envoi',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'dernier_envoi', 'created_at', 'updated_at',
        ]

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')

    def validate_destinataires(self, value):
        """Liste d'adresses email — l'erreur NOMME l'adresse fautive."""
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "destinataires doit être une liste d'adresses email.")
        for adresse in value:
            if not isinstance(adresse, str) or '@' not in adresse:
                raise serializers.ValidationError(
                    f'Adresse email invalide : « {adresse} ».')
        return value
