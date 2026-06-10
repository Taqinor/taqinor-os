from rest_framework import serializers
from .models import CompanyProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    signature_url = serializers.SerializerMethodField()

    class Meta:
        model = CompanyProfile
        fields = '__all__'
        read_only_fields = ['logo_key', 'signature_key']

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
