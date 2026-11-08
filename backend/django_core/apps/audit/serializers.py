"""Sérialisation des entrées du Journal d'activité (lecture seule)."""
from typing import Optional
from zoneinfo import ZoneInfo

from django.core.exceptions import FieldDoesNotExist
from rest_framework import serializers

from .models import AuditLog

CASABLANCA = ZoneInfo('Africa/Casablanca')


class AuditLogSerializer(serializers.ModelSerializer):
    utilisateur = serializers.SerializerMethodField()
    action_label = serializers.CharField(
        source='get_action_display', read_only=True)
    module = serializers.SerializerMethodField()
    model = serializers.SerializerMethodField()
    timestamp_local = serializers.SerializerMethodField()
    detail = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            'id', 'action', 'action_label', 'utilisateur', 'actor_username',
            'module', 'model', 'object_id', 'object_repr', 'detail',
            'timestamp', 'timestamp_local', 'via_portail',
        )

    # ENF11 — annotations de retour = type publié au schéma OpenAPI.
    def get_utilisateur(self, obj) -> str:
        if obj.user_id:
            return obj.user.username
        return obj.actor_username or 'Système'

    def get_module(self, obj) -> str:
        return obj.content_type.app_label if obj.content_type_id else ''

    def get_model(self, obj) -> str:
        return obj.content_type.model if obj.content_type_id else ''

    def get_detail(self, obj) -> str:
        """AMON95 — une ligne UPDATE générique (``signals._on_post_save``) ne
        porte que le diff ``changes`` (déjà caviardé, ASEC8) : le Journal le
        rend « Champ : ancien → nouveau » au lieu de « — »."""
        if obj.detail or not isinstance(obj.changes, list):
            return obj.detail or ''
        modele = obj.content_type.model_class() if obj.content_type_id else None
        morceaux = []
        for c in obj.changes[:5]:
            if not isinstance(c, dict):
                continue
            nom = c.get('field') or ''
            try:
                nom = str(modele._meta.get_field(nom).verbose_name).capitalize()
            except (AttributeError, FieldDoesNotExist):  # modèle ou champ disparu : nom brut
                pass
            ancien, nouveau = c.get('old'), c.get('new')
            morceaux.append(f'{nom} : {"—" if ancien in (None, "") else ancien} → '
                            f'{"—" if nouveau in (None, "") else nouveau}')
        if len(obj.changes) > 5:
            morceaux.append(f'… (+{len(obj.changes) - 5})')
        return ' ; '.join(morceaux)

    def get_timestamp_local(self, obj) -> Optional[str]:
        # Affichage Casablanca (la base stocke en UTC).
        if obj.timestamp is None:
            return None
        return obj.timestamp.astimezone(CASABLANCA).isoformat()
