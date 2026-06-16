from rest_framework import serializers
from .models import Client, Lead, LeadActivity
from .devis_auto import champs_manquants, message_manquants


class LeadActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()

    class Meta:
        model = LeadActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'bulk', 'user_nom', 'created_at',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)


class _CurrentCompanyDefault:
    """Société du user courant, injectée CÔTÉ SERVEUR (jamais lue du corps
    de la requête). Satisfait le validateur d'unicité (company, email) qui,
    sinon, exigeait `company` dans le payload — cassait « Nouveau client »."""
    requires_context = True

    def __call__(self, serializer_field):
        return serializer_field.context['request'].user.company


class ClientSerializer(serializers.ModelSerializer):
    devis_count = serializers.SerializerMethodField()
    company = serializers.HiddenField(default=_CurrentCompanyDefault())

    class Meta:
        model = Client
        fields = '__all__'

    def get_devis_count(self, obj):
        return obj.devis.count()


class LeadSerializer(serializers.ModelSerializer):
    stage_label = serializers.CharField(source='get_stage_display', read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)
    client_nom = serializers.SerializerMethodField()
    devis = serializers.SerializerMethodField()
    owner_nom = serializers.SerializerMethodField()
    owner_poste = serializers.SerializerMethodField()
    owner_avatar = serializers.SerializerMethodField()
    devis_auto = serializers.SerializerMethodField()
    next_activity = serializers.SerializerMethodField()

    def get_devis_auto(self, obj):
        """Prêt pour le devis automatique ? Même règle que l'endpoint
        POST /leads/<id>/devis-auto/ (source unique : devis_auto.py)."""
        manquants = champs_manquants(obj)
        return {
            'pret': not manquants,
            'manquants': manquants,
            'message': message_manquants(manquants) if manquants else None,
        }

    def get_next_activity(self, obj):
        """Activité ouverte la plus proche (pour la pastille horloge de la
        carte kanban) : {state: overdue/today/upcoming, due_date, summary}."""
        try:
            from django.contrib.contenttypes.models import ContentType
            from apps.records.models import Activity
            from apps.records.serializers import activity_state
            ct = ContentType.objects.get_for_model(obj.__class__)
            act = (Activity.objects
                   .filter(content_type=ct, object_id=obj.id, done=False,
                           due_date__isnull=False)
                   .order_by('due_date').first())
            if act is None:
                return None
            return {
                'state': activity_state(act.due_date, False),
                'due_date': act.due_date.isoformat(),
                'summary': act.summary or act.activity_type.nom,
            }
        except Exception:
            return None

    def get_owner_nom(self, obj):
        return getattr(obj.owner, 'username', None)

    def get_owner_poste(self, obj):
        return getattr(obj.owner, 'poste', None) or None

    def get_owner_avatar(self, obj):
        """URL présignée de la photo du responsable (avatar Odoo)."""
        if not obj.owner_id:
            return None
        from authentication.avatars import presign_avatar
        return presign_avatar(getattr(obj.owner, 'avatar_key', ''))

    def validate_owner(self, value):
        # Le responsable assigné doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    class Meta:
        model = Lead
        fields = '__all__'
        # company/source/external refs are set server-side, never trusted from
        # input. The lead→client link is resolved server-side too (no-duplicate
        # rules in services.py), never accepted from the browser.
        # L'archivage se pilote par les actions archiver/restaurer, jamais par
        # un PATCH direct du corps.
        read_only_fields = [
            'company', 'external_system', 'external_id', 'client',
            'is_archived', 'archived_by', 'archived_at',
        ]

    def get_client_nom(self, obj):
        if not obj.client_id:
            return None
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_devis(self, obj):
        # Devis « empilés » sur le lead, du plus récent au plus ancien.
        return [
            {
                'id': d.id,
                'reference': d.reference,
                'statut': d.statut,
                'total_ttc': str(d.total_ttc),
                'date_creation': d.date_creation.isoformat(),
            }
            for d in obj.devis.order_by('-date_creation')
        ]


class LeadTagSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import LeadTag
        model = LeadTag
        fields = ['id', 'nom', 'couleur', 'archived']


class MotifPerteSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import MotifPerte
        model = MotifPerte
        fields = ['id', 'nom', 'archived']


class CanalSerializer(serializers.ModelSerializer):
    # Nombre de leads utilisant ce canal — l'UI désactive la suppression si > 0.
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import Canal
        model = Canal
        fields = ['id', 'cle', 'libelle', 'ordre', 'protege', 'archived', 'en_usage']
        read_only_fields = ['protege']

    def get_en_usage(self, obj):
        from .models import Lead
        return Lead.objects.filter(company=obj.company, canal=obj.cle).count()

    def validate_cle(self, value):
        # La clé d'un canal protégé (ex. 'site_web') ne peut pas être renommée :
        # le webhook du site web en dépend.
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'un canal protégé ne peut pas être modifiée.")
        return value
