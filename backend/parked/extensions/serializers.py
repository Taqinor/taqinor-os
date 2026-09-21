from rest_framework import serializers

from .models import ExtensionPackage


class ExtensionPackageSerializer(serializers.ModelSerializer):
    """NTEXT13 — le catalogue est READ-ONLY : aucun champ n'est éditable via
    cette API (l'installation par tenant est une brique séparée, NTEXT14)."""

    class Meta:
        model = ExtensionPackage
        fields = ['id', 'code', 'nom', 'version', 'description', 'categorie',
                  'manifest', 'date_creation']
        read_only_fields = fields
