from rest_framework import serializers

from . import selectors
from .models import Appel, VoipIdentifiantUtilisateur, VoipParametres


class VoipParametresSerializer(serializers.ModelSerializer):
    est_configure = serializers.BooleanField(read_only=True)

    class Meta:
        model = VoipParametres
        fields = [
            'id', 'fournisseur', 'actif', 'serveur_sip', 'configuration',
            'est_configure',
        ]
        read_only_fields = ['id']


class VoipIdentifiantUtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoipIdentifiantUtilisateur
        fields = ['id', 'identifiant_sip', 'secret']
        read_only_fields = ['id']
        extra_kwargs = {'secret': {'write_only': True}}


class AppelSerializer(serializers.ModelSerializer):
    cible = serializers.SerializerMethodField()

    class Meta:
        model = Appel
        fields = [
            'id', 'direction', 'numero', 'numero_normalise', 'statut',
            'issue', 'started_at', 'ended_at', 'duree_secondes',
            'fournisseur', 'external_call_id', 'utilisateur', 'cible',
        ]
        read_only_fields = fields

    def get_cible(self, obj):
        return selectors.cible_info(obj)
