from rest_framework import serializers
from .models import (
    ALL_PERMISSIONS, ELEVATED_PERMISSIONS, Role, est_permission_app,
)


class RoleSerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()
    # Liste légère des utilisateurs portant ce rôle (id + nom d'affichage), pour
    # l'expansion « Utilisateurs » dans l'éditeur de rôles (Feature RBAC).
    users = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'nom', 'permissions', 'est_systeme',
                  'users_count', 'users', 'entites_visibles')
        read_only_fields = ('id', 'est_systeme', 'users_count', 'users')
        extra_kwargs = {'entites_visibles': {'required': False}}

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
        # ODY26 — les codes « app visible » (``app_<clé>_voir``) sont acceptés
        # PAR FORME et non par énumération : les lister dans ALL_PERMISSIONS
        # les injecterait dans DIRECTEUR/ADMIN_PERMISSIONS (qui en dérivent) et
        # y figer la liste d'apps du jour ; les énumérer ici recréerait un 2ᵉ
        # registre d'apps côté backend, interdit par le Groupe ODY (registre
        # unique = ``moduleConfigs`` côté front). Aucun risque d'escalade : ces
        # codes ne donnent AUCUN droit, ils RESTREIGNENT ce que le rôle voit.
        invalid = [p for p in value
                   if p not in ALL_PERMISSIONS and not est_permission_app(p)]
        if invalid:
            raise serializers.ValidationError(
                f"Permissions invalides : {invalid}"
            )
        # ── Anti-escalade (ERR5) ──────────────────────────────────────────
        # Seul un administrateur (porteur de ``roles_gerer``, ou superuser)
        # peut octroyer une permission ÉLEVÉE (roles_gerer / prix_achat_voir /
        # journal_activite_voir / marge_voir / cout_non_qualite_voir /
        # ao_rentabilite_voir — AOF2, l'économie d'un appel d'offres).
        # On bloque l'AJOUT d'une telle permission par
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

    def validate_entites_visibles(self, value):
        """NTADM3 — le périmètre ne peut porter que des entités de LA société
        de l'acteur.

        ``ModelSerializer`` dérive un ``PrimaryKeyRelatedField`` sur TOUTES
        les entités : sans ce contrôle, un id d'une AUTRE société serait
        accepté (fuite multi-tenant). Liste vide = aucune restriction, le
        rôle voit toutes les entités (comportement historique)."""
        user = self._request_user()
        company = getattr(user, 'company', None)
        if company is None:
            return value
        etrangeres = [e.code for e in value if e.company_id != company.id]
        if etrangeres:
            raise serializers.ValidationError(
                "Ces entités n'appartiennent pas à votre entreprise : "
                f"{sorted(etrangeres)}.")
        return value

    def validate_nom(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le nom ne peut pas être vide.")
        return value.strip()
