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

    class Meta:
        model = Lead
        fields = '__all__'
        # company/source/external refs are set server-side, never trusted from input.
        read_only_fields = ['company', 'external_system', 'external_id']
