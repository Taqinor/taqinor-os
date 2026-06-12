from rest_framework import serializers
from .models import Client, Lead


class ClientSerializer(serializers.ModelSerializer):
    devis_count = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = '__all__'

    def get_devis_count(self, obj):
        return obj.devis.count()


class LeadSerializer(serializers.ModelSerializer):
    stage_label = serializers.CharField(source='get_stage_display', read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)
    client_nom = serializers.SerializerMethodField()
    devis = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = '__all__'
        # company/source/external refs are set server-side, never trusted from
        # input. The lead→client link is resolved server-side too (no-duplicate
        # rules in services.py), never accepted from the browser.
        read_only_fields = ['company', 'external_system', 'external_id', 'client']

    def get_client_nom(self, obj):
        if not obj.client_id:
            return None
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_devis(self, obj):
        # Devis « empilés » sur le lead, du plus récent au plus ancien.
        return [
            {
                'id': d.id,
                'reference': d.reference,
                'statut': d.statut,
                'total_ttc': str(d.total_ttc),
                'date_creation': d.date_creation.isoformat(),
            }
            for d in obj.devis.order_by('-date_creation')
        ]
