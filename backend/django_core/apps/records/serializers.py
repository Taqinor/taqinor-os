from datetime import date

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import Activity, ActivityType, Attachment, ALLOWED_TARGETS


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
    obj = ct.get_object_for_this_type(pk=object_id)
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
        fields = ['id', 'nom', 'icone', 'ordre', 'delai_defaut_jours',
                  'est_systeme']
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
            'object_id', 'target_model', 'target_label',
            'created_at',
        ]
        read_only_fields = ['done', 'done_at', 'done_by', 'auto_relance',
                            'object_id', 'created_at']

    def get_state(self, obj):
        return activity_state(obj.due_date, obj.done)

    def get_target_model(self, obj):
        ct = obj.content_type
        return f'{ct.app_label}.{ct.model}'

    def get_target_label(self, obj):
        target = obj.content_object
        if target is None:
            return None
        for attr in ('nom', 'reference', 'titre'):
            val = getattr(target, attr, None)
            if val:
                prenom = getattr(target, 'prenom', '') or ''
                return f'{val} {prenom}'.strip() if attr == 'nom' else str(val)
        return str(target)


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
