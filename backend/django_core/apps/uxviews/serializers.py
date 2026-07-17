from rest_framework import serializers

from .models import SavedView


class SavedViewSerializer(serializers.ModelSerializer):
    owner_nom = serializers.SerializerMethodField()
    # NTUX2 — le frontend ne connaît le rôle courant que par son NOM
    # (`state.auth.role_nom`, cf. authSlice.js — aucun id numérique de
    # `roles.Role` n'est exposé côté client) : on dénormalise le nom ici pour
    # que l'écran puisse matcher « ma vue par défaut de rôle » sans requête
    # supplémentaire.
    role_nom = serializers.SerializerMethodField()

    class Meta:
        model = SavedView
        fields = [
            'id', 'ecran', 'nom', 'configuration', 'visibilite',
            'est_defaut_role', 'role', 'role_nom', 'owner', 'owner_nom',
            'created_at', 'updated_at',
        ]
        # `owner`/`company`/`est_defaut_role` sont posés côté serveur — jamais
        # depuis le corps de requête (CLAUDE.md — multi-tenant, jamais accepté
        # côté client). `est_defaut_role` ne bascule QUE via l'action dédiée
        # `definir-par-defaut-role` (garde-fou Directeur/Admin + un seul défaut
        # actif par rôle+écran).
        read_only_fields = ['id', 'owner', 'est_defaut_role', 'created_at', 'updated_at']

    def get_owner_nom(self, obj):
        owner = obj.owner
        if not owner:
            return None
        full = f'{getattr(owner, "first_name", "")} {getattr(owner, "last_name", "")}'.strip()
        return full or getattr(owner, 'username', None) or getattr(owner, 'email', None)

    def get_role_nom(self, obj):
        return obj.role.nom if obj.role_id else None
