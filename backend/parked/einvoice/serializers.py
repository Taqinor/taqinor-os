from rest_framework import serializers

from .models import FactureElectronique, TransmissionDGI


class FactureElectroniqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = FactureElectronique
        fields = [
            'id', 'facture_id', 'facture_ref', 'format', 'mode', 'statut',
            'version', 'xml_key', 'hash_contenu', 'signature_xml',
            'certificat_ref', 'signe_le', 'genere_le', 'date_creation',
        ]
        read_only_fields = fields


class TransmissionDGISerializer(serializers.ModelSerializer):
    class Meta:
        model = TransmissionDGI
        fields = [
            'id', 'einvoice', 'statut', 'reponse_json', 'tentatives',
            'prochaine_tentative', 'date_creation',
        ]
        read_only_fields = fields
