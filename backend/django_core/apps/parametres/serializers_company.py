"""Sérialiseur du profil entreprise (``CompanyProfileSerializer``).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``serializers.py`` sans aucun changement de champ, de validation ni de
comportement (mêmes URLs présignées, mêmes contrôles de société)."""
from rest_framework import serializers

from .models import CompanyProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    signature_url = serializers.SerializerMethodField()
    responsable_defaut_leads_nom = serializers.CharField(
        source='responsable_defaut_leads.username', read_only=True
    )
    default_installer_nom = serializers.CharField(
        source='default_installer.username', read_only=True
    )

    class Meta:
        model = CompanyProfile
        fields = '__all__'
        read_only_fields = ['logo_key', 'signature_key']

    def validate_responsable_defaut_leads(self, value):
        # Le responsable par défaut doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def validate_default_installer(self, value):
        # L'installateur par défaut doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def _validate_tva(self, value, label):
        # Garde-fou TVA (L769) : un taux ne peut pas être laissé VIDE et
        # re-snappé silencieusement au défaut (20/10). Un 0 DÉLIBÉRÉ est
        # parfaitement valide et préservé tel quel ; seul le vide est rejeté.
        if value is None:
            raise serializers.ValidationError(
                f'Le taux de {label} est obligatoire (laissez 0 pour exonéré).')
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                f'Le taux de {label} doit être compris entre 0 et 100 %.')
        return value

    def validate_tva_standard(self, value):
        return self._validate_tva(value, 'TVA standard')

    def validate_tva_panneaux(self, value):
        return self._validate_tva(value, 'TVA panneaux')

    def validate(self, attrs):
        # Commission (L788) : dès qu'un mode actif est choisi (pct_devis /
        # par_kwc), la valeur de commission devient obligatoire — sinon on
        # aurait un mode actif sans barème (commission silencieusement nulle).
        # On résout le mode/valeur effectifs (entrants OU déjà enregistrés)
        # pour rester correct en PATCH partiel.
        inst = self.instance
        mode = attrs.get('commission_mode',
                         getattr(inst, 'commission_mode', 'off'))
        if mode and mode != 'off':
            if 'commission_valeur' in attrs:
                valeur = attrs.get('commission_valeur')
            else:
                valeur = getattr(inst, 'commission_valeur', None)
            if valeur is None:
                raise serializers.ValidationError({
                    'commission_valeur':
                        'La valeur de commission est obligatoire quand un '
                        'mode de commission est actif.',
                })
        return attrs

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
