from rest_framework import serializers
from .models import (
    Appointment, Client, ConcurrentPerte, EquipeCommerciale,
    EtapePlanActivite, ForecastEntry, ForecastSnapshot, Lead, LeadActivity,
    LeadPlaybookProgress, MessageTemplate, ObjectifCommercial, Parrainage,
    PlanActivite, PlanCompte, Playbook, PlaybookEtape,
    PlaybookTache, PointContact, RevueCompte, SiteProfile,
    WebsiteLeadPayload,
)
from .devis_auto import champs_manquants, message_manquants
from .scoring import compute_score, score_label, score_reasons

# ODX13 — ré-export TRANSITOIRE des serializers partenaires/territoires
# (FG234–237) qui vivent encore dans ``apps.compta.serializers``. Ce module
# expose ``apps.crm.serializers`` pour les ViewSets ré-exportés dans
# ``apps/crm/views.py`` et les nouvelles routes ``/api/django/crm/…`` ;
# ODX22 re-logera leur corps ici.
from apps.compta.serializers import (  # noqa: F401,E402
    CommissionPartenaireSerializer,
    PartenaireSerializer,
    SoumissionLeadPartenaireSerializer,
    TerritoireCommercialSerializer,
)


class LeadActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()
    # VX111 — pièce jointe optionnelle sur une note (photo prise depuis
    # mobile). Même forme d'URL que AttachmentSerializer.get_url (proxy
    # Django même origine, jamais MinIO direct) — pas de sérialiseur imbriqué
    # pour rester compatible avec la structure plate consommée par
    # ChatterTimeline côté frontend.
    attachment_url = serializers.SerializerMethodField()
    attachment_filename = serializers.SerializerMethodField()
    attachment_mime = serializers.SerializerMethodField()

    class Meta:
        model = LeadActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'outcome', 'bulk', 'user_nom', 'created_at',
            'attachment_url', 'attachment_filename', 'attachment_mime',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)

    def get_attachment_url(self, obj):
        if not obj.attachment_id:
            return None
        return f'/api/django/records/attachments/{obj.attachment_id}/download/'

    def get_attachment_filename(self, obj):
        return getattr(obj.attachment, 'filename', None)

    def get_attachment_mime(self, obj):
        return getattr(obj.attachment, 'mime', None)


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

    # FG20 — coordonnées personnelles masquées quand le rôle n'a pas
    # ``client_pii_voir``. Source unique des champs PII partagée avec le Lead.
    PII_FIELDS = ('telephone', 'email', 'adresse')

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

    def validate_parent(self, value):
        # XSAL9 — anti-cycle + même société, appliqué ici car DRF n'invoque
        # PAS Model.clean() automatiquement à l'écriture API (seul
        # full_clean() le ferait — jamais appelé sur ce chemin).
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'La société mère doit appartenir à la même société.')
        if self.instance is not None:
            if value.pk == self.instance.pk:
                raise serializers.ValidationError(
                    "Un client ne peut pas être sa propre société mère.")
            seen = {self.instance.pk}
            current = value
            depth = 0
            while current is not None:
                if current.pk in seen or depth > 100:
                    raise serializers.ValidationError(
                        'Cette hiérarchie créerait un cycle.')
                seen.add(current.pk)
                current = current.parent
                depth += 1
        return value

    def get_fields(self):
        fields = super().get_fields()
        # FG20 — masque la PII en LECTURE pour les rôles non autorisés. On rend
        # les champs lecture-seule (plutôt que de les retirer) afin de ne jamais
        # casser une écriture légitime, et on les vide à la sérialisation.
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in fields:
                    fields[name].read_only = True
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in data:
                    data[name] = None
        return data

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
    # FG27 — Score de qualité du lead (lecture seule, calculé à la volée).
    score = serializers.SerializerMethodField()
    score_label = serializers.SerializerMethodField()
    # VX221 — décomposition « pourquoi ce score » (facteurs + points), pour le
    # tooltip du badge. Pure exposition des composantes déjà calculées.
    score_reasons = serializers.SerializerMethodField()
    # FG29 — Âge dans l'étape courante (jours depuis le dernier changement d'étape).
    stage_since_days = serializers.SerializerMethodField()
    # VX98 — auteur de la dernière modification (puce de fraîcheur). Lecture seule.
    updated_by_nom = serializers.CharField(
        source='updated_by.username', read_only=True, default=None)
    # VX243(a) — confiance au niveau du DOSSIER : « archivé par X le … ». Les
    # champs archived_by/archived_at sont posés côté serveur (jamais rendus
    # avant) — on expose ici le NOM de l'archiviste en lecture seule pour que
    # la ligne archivée le montre. Silencieux si le lead n'est pas archivé.
    archived_by_nom = serializers.CharField(
        source='archived_by.username', read_only=True, default=None)

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
        carte kanban) : {state: overdue/today/upcoming, due_date, summary}.

        YOPSB13 — sur une LISTE, ``LeadViewSet.list()`` précharge une carte
        {lead_id: Activity} en UNE requête pour toute la page et la pose dans
        le contexte (``next_activity_map``) : on la préfère quand elle existe
        pour éviter une requête PAR LIGNE (N+1). Sans contexte (ex. detail
        unique, ou appel serializer hors vue), on retombe sur la requête
        individuelle — comportement inchangé."""
        try:
            next_activity_map = self.context.get('next_activity_map')
            if next_activity_map is not None:
                act = next_activity_map.get(obj.id)
            else:
                from django.contrib.contenttypes.models import ContentType
                from apps.records.models import Activity
                ct = ContentType.objects.get_for_model(obj.__class__)
                act = (Activity.objects
                       .filter(content_type=ct, object_id=obj.id, done=False,
                               due_date__isnull=False)
                       .order_by('due_date').first())
            if act is None:
                return None
            from apps.records.serializers import activity_state
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

    # FG27 — Score de qualité (lecture seule)
    def get_score(self, obj):
        return compute_score(obj)

    def get_score_label(self, obj):
        return score_label(compute_score(obj))

    def get_score_reasons(self, obj):
        # VX221 — liste [{facteur, label, points}] triée par points décroissants.
        return score_reasons(obj)

    # FG29 — Âge dans l'étape courante
    def get_stage_since_days(self, obj):
        """Nombre de jours depuis le dernier changement d'étape de ce lead.

        Source : dernière entrée LeadActivity de type MODIFICATION sur le champ
        'stage'. Si aucune → âge depuis la création du lead (première entrée).
        Renvoie None si indétectable.
        """
        try:
            from django.utils import timezone
            # YOPSB13/perf_n1 — sur une LISTE, LeadViewSet.list() précharge une
            # carte {lead_id: dernière date de changement d'étape} en UNE requête
            # (stage_since_map) : sinon c'était 1 requête LeadActivity PAR LIGNE
            # (N+1). Hors contexte (détail) → requête individuelle inchangée.
            stage_since_map = self.context.get('stage_since_map')
            if stage_since_map is not None:
                ref = stage_since_map.get(obj.id) or obj.date_creation
            else:
                from .models import LeadActivity
                last_change = (
                    LeadActivity.objects
                    .filter(lead=obj, kind=LeadActivity.Kind.MODIFICATION,
                            field='stage')
                    .order_by('-created_at')
                    .first()
                )
                ref = last_change.created_at if last_change else obj.date_creation
            if ref is None:
                return None
            now = timezone.now()
            if hasattr(ref, 'tzinfo') and ref.tzinfo is None:
                from django.utils.timezone import make_aware
                ref = make_aware(ref)
            return (now - ref).days
        except Exception:
            return None

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
            'first_contacted_at',  # FG28 — posé server-side uniquement
            'updated_by',  # VX98 — posé server-side (perform_update) uniquement
            # B3 — toiture 3D : pin/contour bruts + conso saisis par le client
            # (webhook site, posés server-side). Exposés en LECTURE SEULE sur la
            # fiche lead pour que la page de conception authentifiée réhydrate la
            # toiture épinglée du client ; jamais réécrits via un PATCH du corps.
            'roof_point', 'roof_outline', 'bill_kwh',
        ]

    # FG20 — coordonnées personnelles masquées sans ``client_pii_voir``.
    PII_FIELDS = ('telephone', 'email', 'adresse', 'whatsapp',
                  'gps_lat', 'gps_lng')

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in fields:
                    fields[name].read_only = True
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in data:
                    data[name] = None
        return data

    def get_client_nom(self, obj):
        if not obj.client_id:
            return None
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_devis(self, obj):
        # Devis « empilés » sur le lead, du plus récent au plus ancien.
        # A4 — on expose le chantier lié (s'il existe) et l'option acceptée pour
        # que la fiche lead propose en ligne « Générer la facture » et « Créer le
        # chantier » (sans doublon) après acceptation.
        # YOPSB13 — sur une LISTE, ``LeadViewSet.list()`` précharge les
        # chantiers de TOUS les devis de la page en UNE requête et la pose
        # dans le contexte (``chantier_map``), pour éviter une requête
        # Installation PAR LIGNE (N+1). Sans contexte, on retombe sur l'appel
        # individuel — comportement inchangé.
        # YOPSB13/perf_n1 — ``obj.devis.order_by(...)`` clone le manager et
        # IGNORE le cache prefetch (``prefetch_related('devis')`` posé par
        # ``LeadViewSet``), ré-exécutant une requête PAR ligne (N+1). On lit le
        # cache via ``.all()`` puis on trie en Python (ordre identique), sans
        # importer le modèle ``ventes`` (frontière inter-app respectée).
        rows = sorted(
            obj.devis.all(),
            key=lambda d: (d.date_creation is not None, d.date_creation),
            reverse=True,
        )
        chantier_map = self.context.get('chantier_map')
        if chantier_map is not None:
            chantiers = {d.id: chantier_map.get(d.id) for d in rows}
        else:
            from apps.installations.selectors import (
                installation_summaries_for_devis,
            )
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


class WebsiteLeadPayloadSerializer(serializers.ModelSerializer):
    """QX16 — surface LECTURE SEULE des payloads bruts du site web, pour que
    « jamais perdre un lead » (webhooks.py) soit vérifiable/actionnable, pas
    juste une promesse en commentaire. Le rejeu s'effectue via l'action
    ``replay`` du viewset (jamais depuis ce sérialiseur, jamais un champ
    modifiable ici)."""
    lead_nom = serializers.CharField(source='lead.nom', read_only=True, default=None)

    class Meta:
        model = WebsiteLeadPayload
        fields = [
            'id', 'company', 'payload', 'remote_addr', 'received_at',
            'processed', 'error', 'lead', 'lead_nom',
        ]
        read_only_fields = fields


class ParrainageSerializer(serializers.ModelSerializer):
    """N98 — parrainage. Société posée côté serveur ; parrain/filleul vérifiés
    appartenir à la même société (multi-tenant)."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    parrain_nom = serializers.CharField(
        source='parrain.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # DC14 — nom du filleul à afficher : le FK lié prime sur le texte libre
    # (``filleul_nom`` peut diverger du client/lead réellement référencé).
    filleul_display_nom = serializers.CharField(read_only=True)

    class Meta:
        model = Parrainage
        fields = [
            'id', 'company', 'parrain', 'parrain_nom', 'filleul_lead',
            'filleul_client', 'filleul_nom', 'filleul_display_nom',
            'statut', 'statut_display',
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


# DC12 — Profil site/énergie réutilisable par client ─────────────────────────

class SiteProfileSerializer(serializers.ModelSerializer):
    """DC12 — profil site/énergie réutilisable, attaché au client.

    Société posée CÔTÉ SERVEUR (HiddenField — jamais lue du corps de requête,
    multi-tenant). Le client référencé doit appartenir à la même société
    (validate_client). Une seule fiche par client (OneToOne)."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())

    class Meta:
        model = SiteProfile
        fields = [
            'id', 'company', 'client',
            'facture_hiver', 'facture_ete', 'ete_differente',
            'conso_mensuelle_kwh', 'tranche_onee', 'raccordement',
            'regularisation_8221', 'type_installation',
            'pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
            'type_toiture', 'surface_toiture_m2', 'orientation',
            'inclinaison_deg', 'ombrage', 'ombrage_notes',
            'gps_lat', 'gps_lng',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_client(self, value):
        req = self.context.get('request')
        if req and value and value.company_id != req.user.company_id:
            raise serializers.ValidationError('Client inconnu.')
        return value


# FG36 — Modèles de messages WhatsApp/SMS ─────────────────────────────────────

class MessageTemplateSerializer(serializers.ModelSerializer):
    """Modèle de message CRM (WhatsApp/SMS). Lecture tout rôle, écriture admin."""
    langue_display = serializers.CharField(
        source='get_langue_display', read_only=True)

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'nom', 'langue', 'langue_display', 'corps',
            'archived', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


# QJ20 — Rendez-vous (visites commerciales/techniques) ───────────────────────

class AppointmentSerializer(serializers.ModelSerializer):
    """QJ20 — Rendez-vous sur un lead.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lu du corps de requête). Le lead doit appartenir à la
    même société (validate_lead).
    ``statut_display`` et ``lead_nom`` sont en lecture seule pour l'UI.
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)

    class Meta:
        model = Appointment
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'scheduled_at', 'statut', 'statut_display',
            'notes', 'reminder_sent', 'created_by',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['reminder_sent', 'created_by',
                            'date_creation', 'date_modification']

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value


# ── FG39 — ObjectifCommercial / KPI Target ────────────────────────────────────

class ObjectifCommercialSerializer(serializers.ModelSerializer):
    """Sérialise un objectif commercial + champs lecture optionnels."""

    owner_nom = serializers.SerializerMethodField()
    metric_display = serializers.SerializerMethodField()
    period_type_display = serializers.SerializerMethodField()

    class Meta:
        model = ObjectifCommercial
        fields = [
            'id', 'company', 'owner', 'owner_nom',
            'metric', 'metric_display',
            'period_type', 'period_type_display',
            'period_year', 'period_month', 'period_quarter',
            'cible', 'notes',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'company', 'created_by', 'date_creation', 'date_modification',
        ]

    def get_owner_nom(self, obj):
        return getattr(obj.owner, 'username', None)

    def get_metric_display(self, obj):
        return obj.get_metric_display()

    def get_period_type_display(self, obj):
        return obj.get_period_type_display()

    def validate(self, attrs):
        pt = attrs.get('period_type', getattr(self.instance, 'period_type', None))
        if pt == 'month' and not attrs.get(
                'period_month', getattr(self.instance, 'period_month', None)):
            raise serializers.ValidationError(
                {'period_month': 'Requis pour un objectif mensuel.'}
            )
        if pt == 'quarter' and not attrs.get(
                'period_quarter', getattr(self.instance, 'period_quarter', None)):
            raise serializers.ValidationError(
                {'period_quarter': 'Requis pour un objectif trimestriel.'}
            )
        month = attrs.get('period_month', getattr(self.instance, 'period_month', None))
        if month is not None and not (1 <= month <= 12):
            raise serializers.ValidationError(
                {'period_month': 'Doit être entre 1 et 12.'}
            )
        quarter = attrs.get('period_quarter', getattr(self.instance, 'period_quarter', None))
        if quarter is not None and not (1 <= quarter <= 4):
            raise serializers.ValidationError(
                {'period_quarter': 'Doit être entre 1 et 4.'}
            )
        return attrs


class ObjectifAttainmentSerializer(serializers.Serializer):
    """Lecture seule — objectif + réalisé + taux d'atteinte."""
    id = serializers.IntegerField()
    metric = serializers.CharField()
    metric_display = serializers.CharField()
    period_type = serializers.CharField()
    period_year = serializers.IntegerField()
    period_month = serializers.IntegerField(allow_null=True)
    period_quarter = serializers.IntegerField(allow_null=True)
    cible = serializers.DecimalField(max_digits=14, decimal_places=2)
    owner = serializers.IntegerField(allow_null=True)
    owner_nom = serializers.CharField(allow_null=True)
    realise = serializers.DecimalField(max_digits=14, decimal_places=2)
    taux = serializers.FloatField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()


# ── FG242 — Suivi des concurrents sur deals perdus ────────────────────────────

class ConcurrentPerteSerializer(serializers.ModelSerializer):
    """FG242 — concurrent gagnant + prix saisis sur un lead perdu.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lue du corps de requête) ; ``saisi_par`` est forcé
    dans ``perform_create``. Le lead doit appartenir à la même société
    (validate_lead). ``lead_nom`` est en lecture seule pour l'UI.
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    saisi_par = serializers.PrimaryKeyRelatedField(read_only=True)
    saisi_par_nom = serializers.SerializerMethodField()
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)

    class Meta:
        model = ConcurrentPerte
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'concurrent_nom', 'concurrent_prix', 'devise', 'motif', 'notes',
            'saisi_par', 'saisi_par_nom', 'saisi_le', 'date_modification',
        ]
        read_only_fields = [
            'saisi_par', 'saisi_le', 'date_modification',
        ]

    def get_saisi_par_nom(self, obj):
        return getattr(obj.saisi_par, 'username', None)

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value

    def validate_concurrent_prix(self, value):
        # Prix optionnel mais jamais négatif (garde Decimal explicite en plus du
        # validateur modèle, pour un message clair côté API).
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le prix du concurrent ne peut pas être négatif.')
        return value

    def validate_concurrent_nom(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError(
                'Le nom du concurrent est obligatoire.')
        return value


class PointContactSerializer(serializers.ModelSerializer):
    """FG204 — point de contact du parcours multi-touch d'un lead.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lue du corps de requête) ; ``saisi_par`` est forcé
    dans ``perform_create``. Le lead doit appartenir à la même société
    (validate_lead). ``date_contact`` est optionnel à la saisie (défaut : now).
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    saisi_par = serializers.PrimaryKeyRelatedField(read_only=True)
    saisi_par_nom = serializers.SerializerMethodField()
    canal_libelle = serializers.CharField(
        source='get_canal_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)
    date_contact = serializers.DateTimeField(required=False)

    class Meta:
        model = PointContact
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'canal', 'canal_libelle', 'source', 'date_contact', 'ordre',
            'detail', 'cout',
            'saisi_par', 'saisi_par_nom', 'saisi_le', 'date_modification',
        ]
        read_only_fields = [
            'saisi_par', 'saisi_le', 'date_modification',
        ]

    def get_saisi_par_nom(self, obj):
        return getattr(obj.saisi_par, 'username', None)

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value

    def validate_cout(self, value):
        # Coût optionnel mais jamais négatif (garde Decimal explicite en plus du
        # validateur modèle, pour un message clair côté API).
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le coût ne peut pas être négatif.')
        return value

    def validate_date_contact(self, value):
        # Si non fourni, retombe sur maintenant (le champ a un default côté
        # serveur via perform_create ; ici on accepte simplement la valeur).
        return value


# ── ZSAL2 — Plans d'activité ─────────────────────────────────────────────────

class EtapePlanActiviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtapePlanActivite
        fields = [
            'id', 'plan', 'ordre', 'activity_type', 'delai_jours',
            'resume_defaut', 'assigne_par_defaut',
        ]


class PlanActiviteSerializer(serializers.ModelSerializer):
    etapes = EtapePlanActiviteSerializer(many=True, read_only=True)

    class Meta:
        model = PlanActivite
        fields = ['id', 'company', 'nom', 'actif', 'date_creation', 'etapes']
        read_only_fields = ['company', 'date_creation']


# ── ZSAL3 — Équipes commerciales (admin CRUD ; le dashboard « Mes équipes »
# lit stats_equipe() séparément, voir views.equipes_statistiques) ────────────

class EquipeCommercialeSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.CharField(
        source='responsable.username', read_only=True, default=None)
    nb_membres = serializers.IntegerField(source='membres.count', read_only=True)

    class Meta:
        model = EquipeCommerciale
        fields = [
            'id', 'company', 'nom', 'responsable', 'responsable_nom',
            'membres', 'nb_membres', 'actif', 'date_creation',
        ]
        read_only_fields = ['company', 'date_creation']


# ── NTCRM4 — Catégories de forecast ──────────────────────────────────────────

class ForecastEntrySerializer(serializers.ModelSerializer):
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    montant_effectif = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    owner_id = serializers.IntegerField(source='lead.owner_id', read_only=True)

    class Meta:
        model = ForecastEntry
        fields = [
            'id', 'lead', 'categorie', 'categorie_display', 'montant_prevu',
            'montant_effectif', 'owner_id', 'commentaire',
            'mis_a_jour_par', 'mis_a_jour_le',
        ]
        read_only_fields = ['mis_a_jour_par', 'mis_a_jour_le']


class ForecastSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastSnapshot
        fields = [
            'id', 'semaine_iso', 'categorie', 'montant_total', 'nb_leads',
            'owner', 'created_at',
        ]
        read_only_fields = fields


# ── NTCRM10 — Plan de compte ─────────────────────────────────────────────────
# ARC8 — l'historique (chatter) d'un PlanCompte est sérialisé par
# records.serializers.ChatterActivitySerializer (records.Activity), plus aucun
# serializer *Activity maison ici.


class RevueCompteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevueCompte
        fields = [
            'id', 'plan', 'date_revue', 'participants', 'decisions',
            'prochaine_action', 'prochaine_action_date', 'created_by',
            'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']


class PlanCompteSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    revues = RevueCompteSerializer(many=True, read_only=True)

    class Meta:
        model = PlanCompte
        fields = [
            'id', 'client', 'objectifs_strategiques', 'potentiel_estime',
            'concurrents_presents', 'swot_forces', 'swot_faiblesses',
            'swot_opportunites', 'swot_menaces', 'prochaine_revue', 'statut',
            'statut_display', 'created_by', 'mis_a_jour_par', 'revues',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'mis_a_jour_par', 'date_creation', 'date_modification',
        ]


# ── NTCRM12 — Playbooks de vente par étape ───────────────────────────────────

class PlaybookTacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookTache
        fields = ['id', 'etape', 'libelle', 'obligatoire', 'ordre']


class PlaybookEtapeSerializer(serializers.ModelSerializer):
    stage_display = serializers.SerializerMethodField()
    taches = PlaybookTacheSerializer(many=True, read_only=True)

    class Meta:
        model = PlaybookEtape
        fields = ['id', 'playbook', 'stage', 'stage_display', 'ordre', 'taches']

    def get_stage_display(self, obj):
        from . import stages
        return stages.STAGE_LABELS.get(obj.stage, obj.stage)


class PlaybookSerializer(serializers.ModelSerializer):
    etapes = PlaybookEtapeSerializer(many=True, read_only=True)

    class Meta:
        model = Playbook
        fields = ['id', 'nom', 'actif', 'bloquant', 'etapes', 'date_creation']
        read_only_fields = ['date_creation']


class LeadPlaybookProgressSerializer(serializers.ModelSerializer):
    tache_libelle = serializers.CharField(source='tache.libelle', read_only=True)
    tache_obligatoire = serializers.BooleanField(
        source='tache.obligatoire', read_only=True)
    etape_stage = serializers.CharField(source='tache.etape.stage', read_only=True)
    fait_par_nom = serializers.CharField(
        source='fait_par.username', read_only=True, default=None)

    class Meta:
        model = LeadPlaybookProgress
        fields = [
            'id', 'lead', 'tache', 'tache_libelle', 'tache_obligatoire',
            'etape_stage', 'fait', 'fait_par', 'fait_par_nom', 'fait_le',
            'created_at',
        ]
        read_only_fields = ['fait_par', 'fait_le', 'created_at']
