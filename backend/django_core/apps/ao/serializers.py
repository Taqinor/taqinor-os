"""Serializers du module Appels d'offres (``apps.ao``).

AOF3 — le CORPS des 8 serializers AO vit désormais ICI (il vivait encore
interleavé dans ``apps.compta.serializers``, où toute évolution du domaine AO
aurait forcé la lane à écrire hors de son périmètre). ``company`` n'est JAMAIS
un champ exposé : elle est posée côté serveur par le socle
``CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import (
    AppelOffre,
    BatimentAO,
    BordereauPrix,
    CautionSoumission,
    ChaineCotes,
    DossierSoumission,
    EcheanceAO,
    ExigenceCPS,
    LigneBordereau,
    ObstacleAO,
    PieceConsultation,
    PieceSoumission,
    PlanSource,
    ResultatAO,
    ToitureAO,
)


# ── FG222 — Appels d'offres ────────────────────────────────────────────────

class AppelOffreSerializer(serializers.ModelSerializer):
    type_marche_display = serializers.CharField(
        source='get_type_marche_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # AOF5 — la référence n'est plus obligatoire à la création : laissée vide,
    # elle est générée côté serveur (``AO-YYYYMM-0001``) par
    # ``core.numbering``. Fournie explicitement, elle est respectée (reprise
    # d'un dossier historique).
    reference = serializers.CharField(
        max_length=120, required=False, allow_blank=True)
    # AOF12 — le projet complet. ``date_fin_validite_offre`` est DÉRIVÉE
    # (jamais stockée) ; ``mode_passation_display`` sert l'affichage FR.
    mode_passation_display = serializers.CharField(
        source='get_mode_passation_display', read_only=True)
    date_fin_validite_offre = serializers.DateField(read_only=True)
    # AOF18 — agrégats CALCULÉS (jamais des colonnes recopiées).
    surface_toitures_m2 = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True)
    engagement_modules_batiments = serializers.IntegerField(read_only=True)

    class Meta:
        model = AppelOffre
        fields = [
            'id', 'reference', 'reference_acheteur', 'objet', 'acheteur',
            'maitre_ouvrage', 'soumissionnaire', 'groupement',
            'groupement_membres', 'site_adresse', 'site_gps_lat',
            'site_gps_lng', 'mode_passation', 'mode_passation_display',
            'reference_cps', 'type_marche', 'type_marche_display', 'lot',
            'date_limite', 'date_ouverture_plis', 'validite_offre_jours',
            'date_fin_validite_offre', 'delai_execution_jours',
            'nombre_exemplaires', 'engagement_modules',
            'engagement_modules_batiments', 'surface_toitures_m2',
            'montant_estime', 'montant_offre_ht', 'montant_offre_ttc',
            'caution_provisoire', 'statut', 'statut_display', 'lead_id',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── AOF18 — Bâtiments et toitures ──────────────────────────────────────────

class ToitureAOSerializer(serializers.ModelSerializer):
    forme_display = serializers.CharField(
        source='get_forme_display', read_only=True)
    type_couverture_display = serializers.CharField(
        source='get_type_couverture_display', read_only=True)
    #: CALCULÉE depuis le contour — jamais saisie.
    surface_m2 = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = ToitureAO
        fields = [
            'id', 'batiment', 'code_document', 'designation', 'forme',
            'forme_display', 'contour_local_m', 'angle_nord_deg',
            'rayon_ext_m', 'largeur_m', 'arc_segments', 'murets', 'niveau',
            'altitude_m', 'type_couverture', 'type_couverture_display',
            'contraintes_structure', 'surface_m2',
        ]

    def validate(self, attrs):
        """Applique les refus du modèle AVANT l'écriture.

        DRF n'appelle PAS ``Model.clean()`` : sans ce pont, un polygone qui se
        croise ou un arc sans rayon passerait par l'API alors que le modèle les
        refuse — la garde ne vaudrait que pour l'admin Django.
        """
        instance = self.instance or ToitureAO()
        donnees = {**{
            champ: getattr(instance, champ)
            for champ in ('forme', 'contour_local_m', 'rayon_ext_m',
                          'largeur_m')
        }, **{k: v for k, v in attrs.items() if k in (
            'forme', 'contour_local_m', 'rayon_ext_m', 'largeur_m')}}
        sonde = ToitureAO(**donnees)
        sonde.clean()
        return attrs


class ChaineCotesSerializer(serializers.ModelSerializer):
    """AOF23 — la chaîne, sa fermeture et ses cotes à confirmer."""
    axe_display = serializers.CharField(
        source='get_axe_display', read_only=True)
    verdict_display = serializers.CharField(
        source='get_verdict_display', read_only=True)
    #: Résidus CALCULÉS et persistés — jamais saisis.
    residu_m = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True, allow_null=True)
    residu_pct = serializers.DecimalField(
        max_digits=8, decimal_places=3, read_only=True, allow_null=True)
    verdict = serializers.CharField(read_only=True)
    somme_segments_m = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True)
    cotes_a_confirmer = serializers.ListField(read_only=True)

    class Meta:
        model = ChaineCotes
        fields = [
            'id', 'toiture', 'libelle', 'axe', 'axe_display', 'segments',
            'mesure_totale_m', 'tolerance_m', 'somme_segments_m', 'residu_m',
            'residu_pct', 'verdict', 'verdict_display', 'cotes_a_confirmer',
        ]


class ObstacleAOSerializer(serializers.ModelSerializer):
    """AOF22 — l'obstacle, sa PROVENANCE et la règle de dégagement appliquée."""
    nature_display = serializers.CharField(
        source='get_nature_display', read_only=True)
    provenance_display = serializers.CharField(
        source='get_provenance_display', read_only=True)
    #: Peut-on S'ENGAGER dessus ? Dérivé de la provenance, jamais saisi.
    engageable = serializers.BooleanField(read_only=True)
    est_ecarte = serializers.BooleanField(read_only=True)
    #: La règle EFFECTIVEMENT appliquée, en clair — écrite dans le résultat.
    regle_degagement = serializers.CharField(read_only=True)
    degagement_m = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False)

    class Meta:
        model = ObstacleAO
        fields = [
            'id', 'toiture', 'repere', 'designation', 'nature',
            'nature_display', 'rect_x0_m', 'rect_x1_m', 'rect_y0_m',
            'rect_y1_m', 'polygone_local_m', 'hauteur_m', 'provenance',
            'provenance_display', 'degagement_m', 'degagement_surcharge',
            'motif_surcharge', 'regle_degagement', 'engageable', 'est_ecarte',
            'hors_zone_pv', 'actif', 'decision',
        ]

    def validate(self, attrs):
        surcharge = attrs.get(
            'degagement_surcharge',
            getattr(self.instance, 'degagement_surcharge', False))
        motif = attrs.get(
            'motif_surcharge',
            getattr(self.instance, 'motif_surcharge', ''))
        if surcharge and not (motif or '').strip():
            raise serializers.ValidationError({'motif_surcharge': (
                'Une surcharge de dégagement exige un motif : une valeur '
                "retouchée sans justification n'est pas défendable devant le "
                "maître d'ouvrage."
            )})
        return attrs


class PlanSourceSerializer(serializers.ModelSerializer):
    """AOF20 — les 3 portes d'entrée sont UN CHAMP (``origine``)."""
    origine_display = serializers.CharField(
        source='get_origine_display', read_only=True)
    etat_display = serializers.CharField(
        source='get_etat_display', read_only=True)
    #: DÉRIVÉE des deux points de calibration — jamais saisie.
    echelle_m_par_px = serializers.DecimalField(
        max_digits=14, decimal_places=8, read_only=True)
    distance_calibration_px = serializers.FloatField(
        read_only=True, allow_null=True)

    class Meta:
        model = PlanSource
        fields = [
            'id', 'toiture', 'batiment', 'origine', 'origine_display',
            'type_fichier', 'attachment', 'piece_consultation', 'page',
            'calib_point_a_px',
            'calib_point_b_px', 'calib_distance_reelle_m',
            'distance_calibration_px', 'echelle_m_par_px', 'origine_px',
            'rotation_deg', 'miroir_x', 'miroir_y', 'empreinte_sha256',
            'etat', 'etat_display', 'fourni_par',
        ]
        read_only_fields = ['empreinte_sha256']

    def validate(self, attrs):
        instance = self.instance or PlanSource()
        donnees = {
            'toiture_id': attrs.get(
                'toiture', getattr(instance, 'toiture', None)),
            'batiment_id': attrs.get(
                'batiment', getattr(instance, 'batiment', None)),
        }
        if donnees['toiture_id'] is None and donnees['batiment_id'] is None:
            raise serializers.ValidationError({'toiture': (
                'Un support de plan se rattache à une toiture ou, à défaut, à '
                'un bâtiment : sans rattachement, sa provenance est perdue.'
            )})
        return attrs


class BatimentAOSerializer(serializers.ModelSerializer):
    toitures = ToitureAOSerializer(many=True, read_only=True)
    #: Agrégat CALCULÉ (somme des toitures), jamais une colonne recopiée.
    surface_toitures_m2 = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = BatimentAO
        fields = [
            'id', 'appel_offre', 'code', 'designation', 'ordre',
            'engagement_modules', 'notes', 'toitures', 'surface_toitures_m2',
        ]


# ── AOF14 — Exigences du CPS ───────────────────────────────────────────────

class PieceConsultationSerializer(serializers.ModelSerializer):
    """AOF21 — le DCE REÇU de l'acheteur, pièce par pièce."""
    type_piece_display = serializers.CharField(
        source='get_type_piece_display', read_only=True)
    est_additif = serializers.BooleanField(read_only=True)

    class Meta:
        model = PieceConsultation
        fields = [
            'id', 'appel_offre', 'type_piece', 'type_piece_display',
            'est_additif', 'reference', 'version', 'date_reception',
            'attachment', 'pages_indexees', 'empreinte_sha256', 'modifie',
        ]
        read_only_fields = ['empreinte_sha256']


class ExigenceCPSSerializer(serializers.ModelSerializer):
    type_exigence_display = serializers.CharField(
        source='get_type_exigence_display', read_only=True)
    est_intervalle = serializers.BooleanField(read_only=True)

    class Meta:
        model = ExigenceCPS
        fields = [
            'id', 'appel_offre', 'code', 'libelle', 'type_exigence',
            'type_exigence_display', 'valeur_num', 'valeur_max_num',
            'est_intervalle', 'unite', 'valeur_texte', 'source_piece',
            'source_page', 'piece_consultation', 'a_reverifier', 'bloquant',
            'commentaire',
        ]


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
    # AOF16 — alerte : une caution périmée le jour de l'ouverture fait rejeter
    # le pli. ``None`` quand une des deux dates manque (jamais un faux « OK »).
    expire_avant_ouverture = serializers.BooleanField(
        read_only=True, allow_null=True)

    class Meta:
        model = CautionSoumission
        fields = [
            'id', 'appel_offre', 'type_caution', 'type_caution_display',
            'montant', 'banque', 'reference_acte', 'attachment',
            'date_emission', 'date_echeance', 'date_restitution',
            'expire_avant_ouverture', 'statut', 'statut_display',
            'date_creation',
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
