from rest_framework import serializers
from .models import Role, ALL_PERMISSIONS


class RoleSerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'nom', 'permissions', 'est_systeme', 'users_count')
        read_only_fields = ('id', 'est_systeme', 'users_count')

    def get_users_count(self, obj):
        return obj.users.count()

    def validate_permissions(self, value):
        invalid = [p for p in value if p not in ALL_PERMISSIONS]
        if invalid:
            raise serializers.ValidationError(
                f"Permissions invalides : {invalid}"
            )
        return value

    def validate_nom(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le nom ne peut pas être vide.")
        return value.strip()
