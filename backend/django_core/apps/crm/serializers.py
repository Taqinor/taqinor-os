from rest_framework import serializers
from .models import Client, Lead, LeadActivity, Parrainage
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
    total_facture_ttc = serializers.SerializerMethodField()
    total_paye = serializers.SerializerMethodField()
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    # Traçabilité (L16) : qui a créé le client + dernière modification.
    # created_by est forcé côté serveur (perform_create) — jamais lu du corps.
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_nom = serializers.SerializerMethodField()

    def validate(self, attrs):
        # Champs personnalisés (T11, L808) : valider/nettoyer le custom_data du
        # client contre les définitions du module « client », même chemin que
        # Lead. À la création on valide toujours (champs obligatoires) ; en
        # mise à jour, uniquement si custom_data est fourni.
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'client', company, attrs.get('custom_data'))
        return attrs

    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ['date_modification']

    def get_created_by_nom(self, obj):
        return getattr(obj.created_by, 'username', None)

    def get_devis_count(self, obj):
        return obj.devis.count()

    def get_total_facture_ttc(self, obj):
        """Valeur cumulée FACTURÉE (TTC) du client : somme des factures non
        annulées. total_ttc est une propriété calculée → agrégation en Python.
        Aucun prix d'achat ni marge n'intervient (totaux client-facing)."""
        from decimal import Decimal
        total = Decimal('0')
        for f in obj.factures.all():
            if f.statut != 'annulee':
                total += f.total_ttc
        return str(total)

    def get_total_paye(self, obj):
        """Total ENCAISSÉ du client (somme des montant_paye des factures)."""
        from decimal import Decimal
        total = Decimal('0')
        for f in obj.factures.all():
            if f.statut != 'annulee':
                total += f.montant_paye
        return str(total)


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

    @staticmethod
    def _canonical_phone(value):
        """Forme canonique '212XXXXXXXXX' d'un numéro marocain saisi librement
        (06 12-34 56 78, +212612…, 00212…). Source unique : le normaliseur des
        ventes (apps.ventes.utils.phone) — pas de logique dupliquée ici. Vide
        ou non normalisable → on conserve la valeur saisie telle quelle (jamais
        de rejet : le formulaire est volontairement permissif)."""
        if value in (None, ''):
            return value
        from apps.ventes.utils.phone import normalize_ma_phone
        return normalize_ma_phone(value) or value

    def validate_telephone(self, value):
        return self._canonical_phone(value)

    def validate_whatsapp(self, value):
        return self._canonical_phone(value)

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

    def validate_canal(self, value):
        """Le canal doit appartenir aux canaux GÉRÉS de la société (Paramètres →
        CRM) en plus des choices figés du modèle. Vide accepté. Source unique :
        le référentiel Canal — un PATCH avec une clé inconnue est rejeté 400."""
        if value in (None, ''):
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        from .models import Canal as CanalModel
        existe = CanalModel.objects.filter(
            company=company, cle=value, archived=False).exists()
        # Le référentiel peut ne pas être amorcé (lazy seed) : on tolère alors
        # les clés du modèle pour ne pas casser un import/création légitime.
        if not existe and CanalModel.objects.filter(company=company).exists():
            raise serializers.ValidationError('Canal inconnu.')
        return value

    def validate(self, attrs):
        # Garde funnel côté serveur (aligné sur la règle bulk _bulk_stage_allowed):
        # en MISE À JOUR, un lead perdu ne change pas d'étape, et on ne recule
        # jamais dans l'entonnoir (Froid = parking, jamais une régression).
        if self.instance is not None and 'stage' in attrs:
            from .services import _bulk_stage_allowed
            current = self.instance.stage
            target = attrs['stage']
            if target != current:
                if self.instance.perdu:
                    raise serializers.ValidationError(
                        {'stage': 'Lead perdu — étape non modifiable.'})
                if not _bulk_stage_allowed(current, target):
                    raise serializers.ValidationError(
                        {'stage': "On ne recule pas une étape."})
        # Champs personnalisés (T11) : valider/nettoyer contre les définitions
        # du module « lead ». À la création on valide toujours (champs
        # obligatoires) ; en mise à jour, uniquement si custom_data est fourni
        # (pour ne pas bloquer un PATCH d'un autre champ / édition en place).
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'lead', company, attrs.get('custom_data'))
        return attrs

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
        # A4 — on expose le chantier lié (s'il existe) et l'option acceptée pour
        # que la fiche lead propose en ligne « Générer la facture » et « Créer le
        # chantier » (sans doublon) après acceptation. Une seule requête
        # Installation pour tous les devis du lead.
        from apps.installations.selectors import (
            installation_summaries_for_devis,
        )
        rows = list(obj.devis.order_by('-date_creation'))
        chantiers = installation_summaries_for_devis(rows)
        return [
            {
                'id': d.id,
                'reference': d.reference,
                'statut': d.statut,
                'total_ttc': str(d.total_ttc),
                'date_creation': d.date_creation.isoformat(),
                'option_acceptee': d.option_acceptee,
                'chantier': chantiers.get(d.id),
            }
            for d in rows
        ]


def _tag_en_usage(company, nom):
    """Nombre de leads dont le champ texte ``tags`` référence ce libellé.

    ``Lead.tags`` est un texte libre séparé par des virgules ; on compte les
    leads qui portent ce libellé comme jeton (insensible à la casse)."""
    from .models import Lead
    nom = (nom or '').strip()
    if not nom:
        return 0
    cible = nom.casefold()
    n = 0
    for raw in Lead.objects.filter(
            company=company, tags__icontains=nom).values_list('tags', flat=True):
        if any((t or '').strip().casefold() == cible
               for t in (raw or '').split(',')):
            n += 1
    return n


def _motif_en_usage(company, nom):
    """Nombre de leads dont ``motif_perte`` (texte libre) vaut ce libellé."""
    from .models import Lead
    nom = (nom or '').strip()
    if not nom:
        return 0
    return Lead.objects.filter(
        company=company, motif_perte__iexact=nom).count()


class LeadTagSerializer(serializers.ModelSerializer):
    # Nombre de leads référençant cette étiquette — l'UI désactive la
    # suppression et propose l'archivage si > 0 (L780).
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import LeadTag
        model = LeadTag
        fields = ['id', 'nom', 'couleur', 'archived', 'en_usage']

    def get_en_usage(self, obj):
        return _tag_en_usage(obj.company, obj.nom)


class MotifPerteSerializer(serializers.ModelSerializer):
    # Nombre de leads utilisant ce motif de perte (L779).
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import MotifPerte
        model = MotifPerte
        fields = ['id', 'nom', 'archived', 'en_usage']

    def get_en_usage(self, obj):
        return _motif_en_usage(obj.company, obj.nom)


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


class ParrainageSerializer(serializers.ModelSerializer):
    """N98 — parrainage. Société posée côté serveur ; parrain/filleul vérifiés
    appartenir à la même société (multi-tenant)."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    parrain_nom = serializers.CharField(
        source='parrain.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Parrainage
        fields = [
            'id', 'company', 'parrain', 'parrain_nom', 'filleul_lead',
            'filleul_client', 'filleul_nom', 'statut', 'statut_display',
            'recompense', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def _same_company(self, obj):
        req = self.context.get('request')
        return not (obj and req and obj.company_id != req.user.company_id)

    def validate_parrain(self, value):
        if not self._same_company(value):
            raise serializers.ValidationError('Client inconnu.')
        return value

    def validate_filleul_client(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Client inconnu.')
        return value

    def validate_filleul_lead(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Lead inconnu.')
        return value
