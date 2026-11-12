"""Sérialisation des entrées du Journal d'activité (lecture seule)."""
from typing import Optional
from zoneinfo import ZoneInfo

from django.core.exceptions import FieldDoesNotExist
from rest_framework import serializers

from .models import AuditLog

CASABLANCA = ZoneInfo('Africa/Casablanca')

#: ALEC14 — champs du journal générique sous droit : (app, modèle, champ) →
#: propriété de l'utilisateur qui en autorise la lecture (table unique).
CHAMPS_SOUS_DROIT = {
    ('ventes', 'devis', 'marge_snapshot'): 'can_view_marge',
    ('sav', 'ticket', 'cout'): 'can_view_buy_prices',
    ('stock', 'mouvementstock', 'cout_unitaire'): 'can_view_buy_prices',
}


def champs_caches(entree, user):
    """ALEC14 — champs de ``entree`` que ``user`` n'a pas le droit de lire."""
    ct = entree.content_type if user is not None and entree.content_type_id else None
    return {champ for (app, modele, champ), prop in CHAMPS_SOUS_DROIT.items()
            if ct and (app, modele) == (ct.app_label, ct.model) and not getattr(user, prop, True)}


def ligne_entierement_cachee(entree, user):
    """ALEC14 — une ligne dont le diff ne porte QUE des champs cachés disparaît."""
    caches, ch = champs_caches(entree, user), entree.changes
    return bool(caches and isinstance(ch, list) and ch) and all(
        isinstance(c, dict) and c.get('field') in caches for c in ch)


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
        caches = champs_caches(obj, getattr(self.context.get('request'), 'user', None))  # ALEC14
        changes = [c for c in obj.changes if not (isinstance(c, dict) and c.get('field') in caches)]
        modele = obj.content_type.model_class() if obj.content_type_id else None
        morceaux = []
        for c in changes[:5]:
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
        if len(changes) > 5:
            morceaux.append(f'… (+{len(changes) - 5})')
        return ' ; '.join(morceaux)

    def get_timestamp_local(self, obj) -> Optional[str]:
        # Affichage Casablanca (la base stocke en UTC).
        if obj.timestamp is None:
            return None
        return obj.timestamp.astimezone(CASABLANCA).isoformat()
