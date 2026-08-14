from rest_framework import serializers

from .models import DossierExport, ParametresDouane, PieceDossierExport


class PieceDossierExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceDossierExport
        fields = [
            'id', 'dossier', 'type_piece', 'statut_piece', 'date_depot',
            'attachment', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DossierExportSerializer(serializers.ModelSerializer):
    pieces = PieceDossierExportSerializer(many=True, read_only=True)

    class Meta:
        model = DossierExport
        fields = [
            'id', 'numero', 'devis', 'facture', 'incoterm',
            'port_embarquement', 'port_debarquement', 'pays_destinataire',
            'statut', 'devise', 'valeur_marchandise_devise', 'note',
            'created_by', 'created_at', 'updated_at', 'pieces',
        ]
        read_only_fields = [
            'id', 'numero', 'created_by', 'created_at', 'updated_at', 'pieces',
        ]


class ParametresDouaneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresDouane
        fields = [
            'id', 'regime_douanier_par_defaut', 'alerte_expiration_jours',
            'mention_estimation_droits',
        ]
        read_only_fields = ['id']
