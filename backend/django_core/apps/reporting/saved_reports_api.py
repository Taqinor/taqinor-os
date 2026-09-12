"""N79 — API CRUD des rapports sauvegardés (SavedReport).

Multi-tenant strict via `TenantMixin` : le queryset est borné à la société de
l'utilisateur, `company` est FORCÉE côté serveur (jamais lue du corps), `owner`
est posé sur l'utilisateur courant. Aucun prix d'achat / marge n'apparaît ici
(rien que des métadonnées de rapport).
"""
from rest_framework import serializers, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import EnvoiRapport, SavedReport


class SavedReportSerializer(serializers.ModelSerializer):
    target_kind_label = serializers.CharField(
        source='get_target_kind_display', read_only=True)
    schedule_label = serializers.CharField(
        source='get_schedule_display', read_only=True)

    class Meta:
        model = SavedReport
        # company + owner posés côté serveur — jamais lus du corps.
        fields = [
            'id', 'name', 'definition', 'target_kind', 'target_kind_label',
            # NTDATA37 — identifiant du dashboard / de la requête visée.
            'cible_id',
            'schedule', 'schedule_label', 'heure_envoi', 'jour_du_mois',
            'canal', 'recipients', 'destinataires_whatsapp', 'pinned',
            'last_sent_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'target_kind_label', 'schedule_label', 'last_sent_at',
            'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        """NTDATA37 — la règle du modèle, rendue au CHAMP fautif.

        La CIBLE est cherchée DANS LA SOCIÉTÉ de l'appelant : le corps de
        requête ne peut pas faire pointer un abonnement vers le tableau de
        bord du tenant voisin (il partirait par email chaque semaine).
        """
        instance = getattr(self, 'instance', None)
        kind = attrs.get('target_kind',
                         getattr(instance, 'target_kind', None)
                         or SavedReport.TargetKind.SALES)
        cible = attrs.get('cible_id', getattr(instance, 'cible_id', None))
        if kind in SavedReport.KINDS_AVEC_CIBLE:
            if cible is None:
                raise serializers.ValidationError({
                    'cible_id': 'Choisissez le %s à envoyer.'
                                % dict(SavedReport.TargetKind.choices)[
                                    kind].lower()})
            requete = self.context.get('request')
            company = getattr(getattr(requete, 'user', None), 'company', None)
            if company is not None:
                sonde = SavedReport(company=company, target_kind=kind,
                                    cible_id=cible)
                if sonde.resoudre_cible() is None:
                    raise serializers.ValidationError({
                        'cible_id': "Cette cible n'existe pas dans votre "
                                    'société.'})
        return attrs


class SavedReportViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des rapports sauvegardés, bornés à la société de l'utilisateur.

    Gestion réservée aux responsables/admins (mêmes rapports qu'ils consultent).
    `company` est forcée par `TenantMixin.perform_create/update` ; `owner` est
    fixé sur l'utilisateur courant à la création."""
    serializer_class = SavedReportSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = SavedReport.objects.all()

    def perform_create(self, serializer):
        # company forcée par TenantMixin ; owner = utilisateur courant.
        serializer.save(company=self.request.user.company,
                        owner=self.request.user)


class EnvoiRapportSerializer(serializers.ModelSerializer):
    """NTDATA40 — une tentative de diffusion, en LECTURE seule."""

    canal_label = serializers.CharField(
        source='get_canal_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)
    rapport_nom = serializers.CharField(
        source='saved_report.name', read_only=True)

    class Meta:
        model = EnvoiRapport
        fields = [
            'id', 'saved_report', 'rapport_nom', 'canal', 'canal_label',
            'destinataires', 'statut', 'statut_label', 'erreur', 'envoye_le',
        ]
        read_only_fields = fields


class EnvoiRapportViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTDATA40 — historique de diffusion des rapports (lecture seule).

    Un journal se consulte, il ne se corrige pas : aucune écriture exposée.
    Multi-tenant strict via ``TenantMixin`` (borné à la société de
    l'utilisateur). Filtrable par ``?saved_report=<id>`` et ``?statut=``
    (ex. ``?statut=echec`` pour ne voir que ce qui n'est pas parti)."""

    serializer_class = EnvoiRapportSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = EnvoiRapport.objects.select_related('saved_report').all()

    def get_queryset(self):
        qs = super().get_queryset()
        rapport = self.request.query_params.get('saved_report')
        if rapport:
            qs = qs.filter(saved_report_id=rapport)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs
