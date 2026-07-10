from datetime import date

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import (
    Activity, ActivityType, Attachment, Comment, Follower, Tag, TaggedItem,
    ALLOWED_TARGETS,
)


def resolve_target(model_label, object_id, company):
    """('crm.lead', 12, company) -> (ContentType, instance) ou lève ValueError.

    Vérifie que le modèle est autorisé ET que l'objet appartient à la société.
    """
    try:
        app_label, model = str(model_label).lower().split('.', 1)
    except ValueError:
        raise ValueError('Cible invalide.')
    if (app_label, model) not in ALLOWED_TARGETS:
        raise ValueError('Type de cible non autorisé.')
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        raise ValueError('Type de cible inconnu.')
    # ERR56 — un `id` inexistant ou de mauvais type (ex. non numérique pour une
    # PK entière) doit produire une 400 propre, jamais un 500 : les appelants ne
    # rattrapent que ValueError, donc on convertit DoesNotExist / TypeError en
    # ValueError ici.
    try:
        obj = ct.get_object_for_this_type(pk=object_id)
    except (ct.model_class().DoesNotExist, ValueError, TypeError):
        raise ValueError('Cible introuvable.')
    obj_company = getattr(obj, 'company_id', None)
    if company is not None and obj_company not in (None, company.id):
        raise ValueError('Cible hors de votre société.')
    return ct, obj


def activity_state(due_date, done):
    """État Odoo de l'activité : done / overdue / today / upcoming / none."""
    if done:
        return 'done'
    if not due_date:
        return 'none'
    today = date.today()
    if due_date < today:
        return 'overdue'
    if due_date == today:
        return 'today'
    return 'upcoming'


class ActivityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityType
        # ZSAL1 — type_suivant/mode_enchainement/delai_jours additifs.
        fields = ['id', 'nom', 'icone', 'ordre', 'delai_defaut_jours',
                  'est_systeme', 'type_suivant', 'mode_enchainement',
                  'delai_jours']
        read_only_fields = ['est_systeme']


class ActivitySerializer(serializers.ModelSerializer):
    activity_type_nom = serializers.CharField(
        source='activity_type.nom', read_only=True)
    activity_type_icone = serializers.CharField(
        source='activity_type.icone', read_only=True)
    assigned_to_nom = serializers.CharField(
        source='assigned_to.username', read_only=True, default=None)
    state = serializers.SerializerMethodField()
    # Cible lisible : "crm.lead" + id (pour les liens du cockpit).
    target_model = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            'id', 'activity_type', 'activity_type_nom', 'activity_type_icone',
            'summary', 'note', 'due_date', 'assigned_to', 'assigned_to_nom',
            'done', 'done_at', 'done_by', 'auto_relance', 'state',
            'personnelle', 'object_id', 'target_model', 'target_label',
            'created_at',
        ]
        read_only_fields = ['done', 'done_at', 'done_by', 'auto_relance',
                            'object_id', 'created_at']

    def get_state(self, obj):
        return activity_state(obj.due_date, obj.done)

    def get_target_model(self, obj):
        ct = obj.content_type
        if ct is None:
            return None
        return f'{ct.app_label}.{ct.model}'

    def get_target_label(self, obj):
        # XKB4 — un à-faire personnel n'a pas de cible métier.
        if obj.content_type_id is None:
            return None
        target = obj.content_object
        if target is None:
            return None
        for attr in ('nom', 'reference', 'titre'):
            val = getattr(target, attr, None)
            if val:
                prenom = getattr(target, 'prenom', '') or ''
                return f'{val} {prenom}'.strip() if attr == 'nom' else str(val)
        return str(target)


class ChatterActivitySerializer(serializers.ModelSerializer):
    """ARC8/ARC9 — enveloppe de LECTURE uniforme d'une entrée de chatter.

    Sérialise une ``records.Activity`` portant une entrée de chatter (``kind``
    renseigné) dans le format commun ``kind/field/field_label/old_value/
    new_value/body/user/created_at`` — le MÊME contrat que consomme le frontend
    (VX23 ChatterTimeline) quelle que soit l'app source. ``UniformChatter-
    Serializer`` (ARC9) réutilise ces mêmes clés pour les 13 modèles maison, si
    bien qu'un seul composant front lit toutes les timelines."""

    user_username = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
    target_model = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'user_username', 'object_id', 'target_model', 'created_at',
        ]
        read_only_fields = fields

    def get_target_model(self, obj):
        ct = obj.content_type
        if ct is None:
            return None
        return f'{ct.app_label}.{ct.model}'


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_nom = serializers.CharField(
        source='uploaded_by.username', read_only=True, default=None)
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            'id', 'filename', 'size', 'mime', 'phase', 'uploaded_by',
            'uploaded_by_nom', 'created_at', 'url',
        ]
        read_only_fields = fields

    def get_url(self, obj):
        # B1 — endpoint Django MÊME ORIGINE (chemin relatif résolu contre
        # l'origine courante : nginx → Django). Le cookie d'auth est envoyé
        # automatiquement. On ne renvoie plus l'URL présignée MinIO, dont
        # l'hôte interne n'est pas joignable depuis le navigateur.
        return f'/api/django/records/attachments/{obj.id}/download/'


class CommentSerializer(serializers.ModelSerializer):
    """FG7 — Commentaire générique avec @mentions."""
    author_username = serializers.CharField(
        source='author.username', read_only=True, default=None)
    author_display = serializers.SerializerMethodField()
    target_model = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'body', 'author', 'author_username', 'author_display',
            'object_id', 'target_model', 'resolved', 'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'author', 'author_username', 'author_display',
            'object_id', 'target_model', 'created_at', 'updated_at',
        ]

    def get_author_display(self, obj):
        if obj.author is None:
            return None
        name = f'{obj.author.first_name} {obj.author.last_name}'.strip()
        return name or obj.author.username

    def get_target_model(self, obj):
        ct = obj.content_type
        return f'{ct.app_label}.{ct.model}'


class TagSerializer(serializers.ModelSerializer):
    """FG9 — Tag du vocabulaire partagé."""
    class Meta:
        model = Tag
        # company posée côté serveur.
        fields = ['id', 'nom', 'couleur', 'created_at']
        read_only_fields = ['id', 'created_at']


class TaggedItemSerializer(serializers.ModelSerializer):
    """FG9 — Association tag ↔ enregistrement."""
    tag_nom = serializers.CharField(source='tag.nom', read_only=True)
    tag_couleur = serializers.CharField(source='tag.couleur', read_only=True)

    class Meta:
        model = TaggedItem
        fields = ['id', 'tag', 'tag_nom', 'tag_couleur', 'object_id', 'created_at']
        read_only_fields = ['id', 'tag_nom', 'tag_couleur', 'object_id', 'created_at']


class FollowerSerializer(serializers.ModelSerializer):
    """XKB34 — abonnement d'un utilisateur à un enregistrement."""
    user_username = serializers.CharField(
        source='user.username', read_only=True, default=None)
    target_model = serializers.SerializerMethodField()

    class Meta:
        model = Follower
        fields = ['id', 'user', 'user_username', 'sous_type', 'object_id',
                  'target_model', 'created_at']
        read_only_fields = ['id', 'user', 'user_username', 'object_id',
                            'target_model', 'created_at']

    def get_target_model(self, obj):
        ct = obj.content_type
        return f'{ct.app_label}.{ct.model}'
