from rest_framework import serializers
from django.utils import timezone

from .models import ContratMaintenance, Equipement, Ticket, TicketActivity

# Fenêtre « garantie expirant bientôt » (jours).
EXPIRING_SOON_DAYS = 90


class EquipementSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True, default=None)
    produit_marque = serializers.CharField(source='produit.marque', read_only=True, default=None)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True, default=None)
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    client_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    garantie_etat = serializers.SerializerMethodField()
    garantie_jours_restants = serializers.SerializerMethodField()

    class Meta:
        model = Equipement
        fields = '__all__'
        # company / dates de garantie / created_by posés côté serveur — jamais
        # depuis le corps. Les dates de garantie sont CALCULÉES (read-only).
        read_only_fields = [
            'company', 'created_by',
            'date_fin_garantie', 'date_fin_garantie_production',
            'date_creation', 'date_modification',
        ]

    def get_client_nom(self, obj):
        c = getattr(obj.installation, 'client', None)
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_garantie_jours_restants(self, obj):
        if not obj.date_fin_garantie:
            return None
        return (obj.date_fin_garantie - timezone.localdate()).days

    def get_garantie_etat(self, obj):
        """État de garantie : non_renseignee / sous_garantie / expire_bientot /
        hors_garantie. Sert d'indicateur clair côté écran."""
        if not obj.date_fin_garantie:
            return 'non_renseignee'
        jours = (obj.date_fin_garantie - timezone.localdate()).days
        if jours < 0:
            return 'hors_garantie'
        if jours <= EXPIRING_SOON_DAYS:
            return 'expire_bientot'
        return 'sous_garantie'


class TicketActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()

    class Meta:
        model = TicketActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'user_nom', 'created_at',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)


class TicketInterventionSerializer(serializers.Serializer):
    """Vue légère des interventions liées à un ticket (lecture seule)."""
    id = serializers.IntegerField()
    type_intervention = serializers.CharField()
    type_intervention_display = serializers.CharField(
        source='get_type_intervention_display')
    installation_id = serializers.IntegerField()
    date_prevue = serializers.DateField()
    date_realisee = serializers.DateField()
    compte_rendu = serializers.CharField()
    technicien_nom = serializers.SerializerMethodField()

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien, 'username', None)


class TicketSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    priorite_display = serializers.CharField(
        source='get_priorite_display', read_only=True)
    statut_ordre = serializers.SerializerMethodField()
    client_nom = serializers.SerializerMethodField()
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    equipement_serie = serializers.CharField(
        source='equipement.numero_serie', read_only=True, default=None)
    equipement_produit = serializers.CharField(
        source='equipement.produit.nom', read_only=True, default=None)
    equipement_fin_garantie = serializers.DateField(
        source='equipement.date_fin_garantie', read_only=True, default=None)
    technicien_nom = serializers.SerializerMethodField()
    # Garantie effective : calculée depuis l'équipement lié, sinon manuelle.
    sous_garantie_effectif = serializers.SerializerMethodField()
    sous_garantie_effectif_display = serializers.SerializerMethodField()
    interventions = TicketInterventionSerializer(many=True, read_only=True)
    nb_interventions = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = '__all__'
        # company / reference / created_by posés côté serveur — jamais du corps.
        read_only_fields = [
            'company', 'reference', 'created_by',
            'date_creation', 'date_modification',
        ]

    def get_statut_ordre(self, obj):
        order = list(Ticket.STATUT_ORDER)
        try:
            return order.index(obj.statut)
        except ValueError:
            return len(order)

    def get_client_nom(self, obj):
        c = obj.client
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien_responsable, 'username', None)

    def get_sous_garantie_effectif(self, obj):
        return obj.sous_garantie_calcule

    def get_sous_garantie_effectif_display(self, obj):
        return dict(Ticket.SousGarantie.choices).get(
            obj.sous_garantie_calcule, obj.sous_garantie_calcule)

    def get_nb_interventions(self, obj):
        return obj.interventions.count()


class ContratMaintenanceSerializer(serializers.ModelSerializer):
    client_nom = serializers.SerializerMethodField()
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    # Échéance + état « due / à venir » — CALCULÉS à la lecture, jamais stockés.
    prochaine_visite = serializers.SerializerMethodField()
    est_due = serializers.SerializerMethodField()
    est_a_venir = serializers.SerializerMethodField()
    jours_avant_visite = serializers.SerializerMethodField()

    class Meta:
        model = ContratMaintenance
        fields = '__all__'
        # company / client / created_by / garde-fou d'idempotence posés côté
        # serveur — jamais lus du corps. client est résolu depuis le chantier.
        read_only_fields = [
            'company', 'client', 'created_by',
            'derniere_echeance_traitee',
            'date_creation', 'date_modification',
        ]

    def get_client_nom(self, obj):
        c = obj.client
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_prochaine_visite(self, obj):
        d = obj.prochaine_visite
        return d.isoformat() if d else None

    def get_est_due(self, obj):
        return obj.est_due()

    def get_est_a_venir(self, obj):
        return obj.est_a_venir()

    def get_jours_avant_visite(self, obj):
        d = obj.prochaine_visite
        if not d:
            return None
        return (d - timezone.localdate()).days
