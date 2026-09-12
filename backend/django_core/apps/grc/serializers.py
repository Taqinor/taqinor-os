"""Sérialiseurs du module GRC & Conformité (NTGRC).

Règle commune : ``company`` n'est JAMAIS lue du corps de la requête — elle est
imposée côté serveur par ``CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import (
    JournalDestruction, LegalHold, PolitiqueRetentionObjet, RisqueEntreprise,
    ViolationDonnees,
)


class PolitiqueRetentionObjetSerializer(serializers.ModelSerializer):
    """NTGRC4 — durée de conservation d'un type d'objet, par société."""

    type_objet_libelle = serializers.CharField(
        source='get_type_objet_display', read_only=True)
    action_echeance_libelle = serializers.CharField(
        source='get_action_echeance_display', read_only=True)

    class Meta:
        model = PolitiqueRetentionObjet
        fields = [
            'id', 'type_objet', 'type_objet_libelle',
            'duree_conservation_mois',
            'action_echeance', 'action_echeance_libelle', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_duree_conservation_mois(self, valeur):
        if valeur is None or int(valeur) < 1:
            raise serializers.ValidationError(
                'La durée de conservation doit valoir au moins 1 mois.')
        return valeur


class JournalDestructionSerializer(serializers.ModelSerializer):
    """NTGRC5 — ligne IMMUABLE du journal de destruction.

    Tout est en lecture seule sauf à la création : une ligne de journal ne se
    réécrit pas. ``company`` est imposée côté serveur.
    """

    action_libelle = serializers.CharField(
        source='get_action_display', read_only=True)

    class Meta:
        model = JournalDestruction
        fields = [
            'id', 'type_objet', 'objet_ref', 'action', 'action_libelle',
            'politique_ref', 'demande_droit_ref', 'executee_par', 'motif',
            'empreinte_avant', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'executee_par']


class ViolationDonneesSerializer(serializers.ModelSerializer):
    """NTGRC6 — violation de données personnelles (registre réglementaire).

    ``reference`` et ``date_echeance_72h`` sont posées CÔTÉ SERVEUR : la
    première par la numérotation race-safe, la seconde par le modèle à la
    création (détection + 72 h). Aucune des deux n'est lue du corps.
    """

    nature_libelle = serializers.CharField(
        source='get_nature_display', read_only=True)
    gravite_libelle = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    echeance_72h_depassee = serializers.SerializerMethodField()

    class Meta:
        model = ViolationDonnees
        fields = [
            'id', 'reference', 'date_detection', 'date_incident',
            'nature', 'nature_libelle', 'categories_donnees',
            'nombre_personnes_estime', 'gravite', 'gravite_libelle',
            'risque_personnes', 'mesures_prises',
            'notification_cndp_requise', 'date_notification_cndp',
            'date_echeance_72h', 'echeance_72h_depassee',
            'personnes_notifiees', 'statut', 'statut_libelle',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'date_echeance_72h', 'statut',
            # La notification CNDP s'enregistre par l'action dédiée
            # `notifier-cndp/` (qui pose la date ET le statut ensemble) —
            # jamais par une écriture de champ qui laisserait le statut mentir.
            'date_notification_cndp',
            'created_at', 'updated_at',
        ]

    def get_echeance_72h_depassee(self, obj):
        """Le délai légal est-il dépassé sans notification ? (lecture seule)"""
        from django.utils import timezone

        if not obj.notification_cndp_requise or obj.date_notification_cndp:
            return False
        if obj.date_echeance_72h is None:
            return False
        return obj.date_echeance_72h < timezone.now()

    def validate(self, attrs):
        """Contrôles de cohérence — le message NOMME le champ fautif."""
        detection = attrs.get(
            'date_detection',
            getattr(self.instance, 'date_detection', None))
        incident = attrs.get(
            'date_incident', getattr(self.instance, 'date_incident', None))
        if detection and incident and incident > detection:
            raise serializers.ValidationError({
                'date_incident': "L'incident ne peut pas être postérieur à sa "
                                 'détection.'})
        return attrs


class LegalHoldSerializer(serializers.ModelSerializer):
    """NTGRC8 — mise sous séquestre transverse (legal hold)."""

    motif_libelle = serializers.CharField(
        source='get_motif_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = LegalHold
        fields = [
            'id', 'nom', 'motif', 'motif_libelle', 'perimetre',
            'date_debut', 'date_fin', 'statut', 'statut_libelle',
            'demandeur', 'base_juridique', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'statut', 'created_at', 'updated_at']

    def validate_perimetre(self, valeur):
        """Le périmètre est une LISTE de ``{type_objet, filtre}``.

        Un périmètre mal formé est refusé à la saisie plutôt que d'être
        silencieusement ignoré à la résolution : un séquestre qui ne gèle rien
        sans le dire est pire que pas de séquestre du tout.
        """
        if valeur in (None, ''):
            return []
        if not isinstance(valeur, list):
            raise serializers.ValidationError(
                'Le périmètre doit être une liste de {type_objet, filtre}.')
        for entree in valeur:
            if not isinstance(entree, dict) or not (
                    entree.get('type_objet') or '').strip():
                raise serializers.ValidationError(
                    'Chaque entrée du périmètre doit porter un '
                    '« type_objet » non vide.')
        return valeur

    def validate(self, attrs):
        debut = attrs.get('date_debut',
                          getattr(self.instance, 'date_debut', None))
        fin = attrs.get('date_fin', getattr(self.instance, 'date_fin', None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({
                'date_fin': 'La date de fin ne peut pas précéder la date de '
                            'début.'})
        return attrs


class RisqueEntrepriseSerializer(serializers.ModelSerializer):
    """NTGRC13 — risque d'entreprise (ERM), cotations inhérente et résiduelle.

    Les deux criticités sont CALCULÉES côté serveur (probabilité × impact) :
    exposées en lecture, jamais saisies — une criticité saisie à la main finit
    toujours par contredire ses deux facteurs.
    """

    categorie_libelle = serializers.CharField(
        source='get_categorie_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = RisqueEntreprise
        fields = [
            'id', 'reference', 'titre', 'categorie', 'categorie_libelle',
            'description', 'proprietaire',
            'probabilite', 'impact', 'criticite_inherente',
            'reponse',
            'probabilite_residuelle', 'impact_residuel',
            'criticite_residuelle',
            'statut', 'statut_libelle', 'date_revue_prevue',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'criticite_inherente', 'criticite_residuelle',
            'created_at', 'updated_at',
        ]

    def _borner(self, champ, valeur):
        mini, maxi = RisqueEntreprise.ECHELLE_MIN, RisqueEntreprise.ECHELLE_MAX
        if valeur is None:
            return valeur
        if not (mini <= int(valeur) <= maxi):
            raise serializers.ValidationError({
                champ: f'La cotation doit valoir entre {mini} et {maxi}.'})
        return valeur

    def validate(self, attrs):
        """Les cotations restent dans la grille — le message nomme le champ."""
        for champ in ('probabilite', 'impact', 'probabilite_residuelle',
                      'impact_residuel'):
            if champ in attrs:
                self._borner(champ, attrs[champ])
        return attrs
