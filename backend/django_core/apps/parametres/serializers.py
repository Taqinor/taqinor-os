from rest_framework import serializers
from .models import CompanyProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    signature_url = serializers.SerializerMethodField()
    responsable_defaut_leads_nom = serializers.CharField(
        source='responsable_defaut_leads.username', read_only=True
    )
    # ROI avec repli sur défauts (pour l'affichage : toujours des valeurs).
    roi_constants_effective = serializers.SerializerMethodField()
    # Défauts historiques exposés pour le bouton « Réinitialiser ».
    roi_constants_defaults = serializers.SerializerMethodField()

    class Meta:
        model = CompanyProfile
        fields = '__all__'
        read_only_fields = ['logo_key', 'signature_key']

    def get_roi_constants_effective(self, obj):
        return obj.roi_constants_effective

    def get_roi_constants_defaults(self, obj):
        from .models import ROI_CONSTANTS_DEFAULTS
        return ROI_CONSTANTS_DEFAULTS

    def validate_responsable_defaut_leads(self, value):
        # Le responsable par défaut doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def _presign(self, key):
        if not key:
            return None
        try:
            from apps.ventes.utils.minio_client import get_minio_client
            from django.conf import settings
            client = get_minio_client()
            return client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.MINIO_BUCKET_UPLOADS, 'Key': key},
                ExpiresIn=3600,
            )
        except Exception:
            return None

    def get_logo_url(self, obj):
        return self._presign(obj.logo_key)

    def get_signature_url(self, obj):
        return self._presign(obj.signature_key)
