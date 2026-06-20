from rest_framework import serializers
from .models import Role, ALL_PERMISSIONS, ELEVATED_PERMISSIONS


class RoleSerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()
    # Liste légère des utilisateurs portant ce rôle (id + nom d'affichage), pour
    # l'expansion « Utilisateurs » dans l'éditeur de rôles (Feature RBAC).
    users = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'nom', 'permissions', 'est_systeme',
                  'users_count', 'users')
        read_only_fields = ('id', 'est_systeme', 'users_count', 'users')

    def get_users_count(self, obj):
        return obj.users.count()

    def get_users(self, obj):
        return [
            {'id': u.id, 'username': u.username}
            for u in obj.users.all()
        ]

    def _request_user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def validate_permissions(self, value):
        invalid = [p for p in value if p not in ALL_PERMISSIONS]
        if invalid:
            raise serializers.ValidationError(
                f"Permissions invalides : {invalid}"
            )
        # ── Anti-escalade (ERR5) ──────────────────────────────────────────
        # Seul un administrateur (porteur de ``roles_gerer``, ou superuser)
        # peut octroyer une permission ÉLEVÉE (roles_gerer / prix_achat_voir /
        # journal_activite_voir). On bloque l'AJOUT d'une telle permission par
        # un non-admin : sans cela, un Responsable coche ``roles_gerer`` sur son
        # rôle et s'auto-promeut Administrateur. On compare aux permissions
        # déjà posées (PATCH partiel : on ne pénalise pas un rôle qui les avait
        # déjà), pour ne bloquer que les permissions AJOUTÉES.
        user = self._request_user()
        if user is not None and not getattr(user, 'is_admin_role', False):
            existing = set(self.instance.permissions or []) if self.instance \
                else set()
            added_elevated = (set(value) & ELEVATED_PERMISSIONS) - existing
            if added_elevated:
                raise serializers.ValidationError(
                    "Seul un administrateur peut octroyer ces permissions "
                    f"élevées : {sorted(added_elevated)}."
                )
        return value

    def validate(self, attrs):
        # ── Garde des rôles système (ERR5) ────────────────────────────────
        # Un non-administrateur ne peut PAS modifier les permissions (ni
        # renommer) un rôle système (``est_systeme=True``) — Administrateur,
        # Directeur, etc. Sans cela un Responsable édite le rôle système qui le
        # porte (ou un autre) pour s'octroyer des droits.
        user = self._request_user()
        if self.instance is not None and self.instance.est_systeme \
                and user is not None \
                and not getattr(user, 'is_admin_role', False):
            touches_perms = 'permissions' in attrs and \
                sorted(attrs['permissions'] or []) != \
                sorted(self.instance.permissions or [])
            touches_nom = 'nom' in attrs and \
                attrs['nom'] != self.instance.nom
            if touches_perms or touches_nom:
                raise serializers.ValidationError(
                    "Seul un administrateur peut modifier un rôle système."
                )
        return attrs

    def validate_nom(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le nom ne peut pas être vide.")
        return value.strip()
