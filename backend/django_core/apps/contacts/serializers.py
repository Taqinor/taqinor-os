from rest_framework import serializers

from .models import ContactClient


class ContactClientSerializer(serializers.ModelSerializer):
    role_achat_display = serializers.CharField(
        source='get_role_achat_display', read_only=True)

    class Meta:
        model = ContactClient
        fields = [
            'id', 'client', 'nom', 'prenom', 'poste', 'email', 'telephone',
            'whatsapp', 'role_achat', 'role_achat_display',
            'contact_principal', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        # Traduit la garde du modèle (clean() : un seul principal par client)
        # en 400 propre côté API plutôt qu'un ValidationError non catché à
        # save() — même contrat pour l'ORM direct et l'API.
        contact_principal = attrs.get(
            'contact_principal',
            self.instance.contact_principal if self.instance else False)
        if contact_principal:
            client = attrs.get('client') or (
                self.instance.client if self.instance else None)
            if client is not None:
                qs = ContactClient.objects.filter(
                    client_id=client.pk, contact_principal=True)
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise serializers.ValidationError({
                        'contact_principal':
                            'Un seul contact principal est autorisé par '
                            'client — un autre contact est déjà marqué '
                            'principal.',
                    })
        return attrs
