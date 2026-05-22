from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    devis_count = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = '__all__'

    def get_devis_count(self, obj):
        return obj.devis.count()
