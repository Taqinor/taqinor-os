"""Sérialiseurs de la couche fondation ``core``.

FG368 — forme de sortie des jobs planifiés (lecture seule, infra globale).
FG369 — forme de sortie des modèles de workflow installables (catalogue).

CRX12 — champ de relation AUTO-SCOPÉ société (primitive plateforme)
--------------------------------------------------------------------

Constat de l'audit CRM (L3, 02/09/2026) : un ``PrimaryKeyRelatedField`` NU
(queryset non scopé, ex. ``Lead.objects.all()``) laisse un client rattacher son
objet à une ligne d'une AUTRE société — et, pire, sert d'ORACLE D'EXISTENCE
(l'erreur « objet inexistant » vs « ok » révèle si l'id existe chez le voisin).
``TenantMixin`` scope le queryset de la VUE, jamais celui des relations
DÉCLARÉES dans le sérialiseur : le trou est structurel, pas ponctuel.

Trois pièces, à composer selon le besoin :

* :class:`CompanyScopedPrimaryKeyRelatedField` — un ``PrimaryKeyRelatedField``
  dont ``get_queryset()`` est re-filtré sur ``request.user.company`` DÈS LORS que
  le modèle cible porte un champ de relation ``company``. Un id hors société
  devient donc un ``ValidationError`` « objet inexistant » standard — le même
  message que pour un id réellement inexistant, donc AUCUN oracle. Utilisable
  seul, y compris avec ``many=True`` (le ``ManyRelatedField`` de DRF délègue au
  ``child_relation``, qui est bien notre classe).
* :func:`scope_related_field` — promeut SUR PLACE un ``PrimaryKeyRelatedField``
  déjà construit (ou le ``child_relation`` d'un ``ManyRelatedField``) en sa
  version scopée. Utile pour re-scoper un champ déclaré à la main sans réécrire
  ses arguments.
* :class:`CompanyScopedRelationsMixin` /
  :class:`CompanyScopedModelSerializer` — base-serializer OPTIONNELLE :
  ``serializer_related_field`` pointe la classe scopée (donc toutes les
  relations AUTO-CONSTRUITES depuis ``Meta.fields`` le sont) ET ``get_fields``
  promeut les relations DÉCLARÉES à la main. Un champ déjà spécialisé (sous-
  classe métier de ``PrimaryKeyRelatedField``) n'est JAMAIS touché.

Non-régression : sans requête dans le contexte (rendu serveur/interne, shell,
tâche Celery) ou pour un superuser SANS société (acteur plateforme supporté, cf.
``core.mixins.TenantMixin``), le queryset est renvoyé INCHANGÉ — comportement
byte-identique à un ``PrimaryKeyRelatedField`` nu. Un superuser AVEC société est
scopé, exactement comme le fait ``TenantMixin`` pour les listes.

``core`` reste FONDATION : aucun import d'app métier ici.
"""
from django.core.exceptions import FieldDoesNotExist
from rest_framework import serializers

from .models import (
    ApiUsagePlan,
    BackgroundJob,
    BackupRun,
    BrandedTemplate,
    ChangelogEntry,
    ConsentRecord,
    Dashboard,
    DataSubjectRequest,
    DeletionRecord,
    ModuleToggle,
    OutboxEvent,
    PaymentTransaction,
    RegistreTraitement,
    SavedQuery,
    ScheduledExport,
    TenantTheme,
    TenantUsageSnapshot,
    WorkflowDefinition,
    WorkflowStepDefinition,
)


# ─────────────────────────────────────────────────────────────────────────────
# CRX12 — Relations auto-scopées société
# ─────────────────────────────────────────────────────────────────────────────

def model_is_company_scoped(model) -> bool:
    """Vrai si ``model`` porte une RELATION ``company`` (modèle multi-tenant).

    Un simple champ texte nommé ``company`` (cas théorique) n'est pas une
    frontière tenant : on exige ``is_relation``.
    """
    if model is None:
        return False
    try:
        field = model._meta.get_field('company')
    except (FieldDoesNotExist, AttributeError):
        return False
    return bool(getattr(field, 'is_relation', False))


def request_company_id(context):
    """Id de société de l'utilisateur de la requête, ou ``None``.

    ``None`` signifie « ne rien scoper » : pas de requête (rendu interne,
    shell, tâche de fond), utilisateur anonyme, ou superuser plateforme SANS
    société — les trois acteurs pour lesquels ``TenantMixin`` ne restreint pas
    non plus.
    """
    request = (context or {}).get('request')
    user = getattr(request, 'user', None) if request is not None else None
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return getattr(user, 'company_id', None)


class CompanyScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """``PrimaryKeyRelatedField`` re-scopé sur la société de la requête.

    Le queryset déclaré est filtré par ``company_id=request.user.company_id``
    quand — et seulement quand — le modèle cible porte une relation
    ``company``. Un id appartenant à une autre société est alors REFUSÉ avec le
    message d'erreur standard « objet inexistant » de DRF : indiscernable d'un
    id qui n'existe pas, donc aucun oracle d'existence inter-tenant.

    Fonctionne à l'identique en ``many=True`` : ``many_init`` de DRF construit
    un ``ManyRelatedField`` dont le ``child_relation`` est une instance de cette
    classe, et c'est lui qui résout chaque id.
    """

    def __init__(self, **kwargs):
        # DRF n'exige un ``queryset`` que si ``get_queryset`` n'est PAS
        # surchargé (``relations.method_overridden``). Comme on le surcharge,
        # l'assertion d'origine est désactivée : on la ré-affirme ici pour ne
        # pas perdre le garde-fou (un champ inscriptible sans queryset échouerait
        # sinon très tard, avec un message obscur).
        super().__init__(**kwargs)
        assert self.queryset is not None or kwargs.get('read_only'), (
            'CompanyScopedPrimaryKeyRelatedField exige un argument `queryset` '
            '(ou read_only=True).'
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        if queryset is None:
            return queryset
        company_id = request_company_id(self.context)
        if company_id is None:
            return queryset
        if not model_is_company_scoped(queryset.model):
            return queryset
        return queryset.filter(company_id=company_id)


def scope_related_field(field):
    """Promeut SUR PLACE un champ de relation en sa version scopée société.

    Accepte un ``PrimaryKeyRelatedField`` ou un ``ManyRelatedField`` (dont le
    ``child_relation`` est alors promu). Renvoie ``True`` si une promotion a eu
    lieu.

    Prudence VOLONTAIRE : seul un champ dont le type est EXACTEMENT
    ``PrimaryKeyRelatedField`` est promu. Une sous-classe métier (validation
    propre, ``get_queryset`` maison, champ déjà scopé…) est laissée intacte —
    on ne remplace jamais un comportement écrit à la main. La promotion se fait
    par réaffectation de ``__class__`` : la classe cible est une sous-classe
    directe qui n'ajoute AUCUN attribut d'instance, donc l'objet (queryset,
    ``source``, ``required``, messages d'erreur, liaison au parent) est conservé
    tel quel — c'est la seule façon de re-scoper un champ déjà construit sans
    ré-inventer ses arguments d'origine.
    """
    child = getattr(field, 'child_relation', None)
    if child is not None:
        return scope_related_field(child)
    if type(field) is not serializers.PrimaryKeyRelatedField:
        return False
    if getattr(field, 'read_only', False) or field.queryset is None:
        return False
    if not model_is_company_scoped(field.queryset.model):
        return False
    field.__class__ = CompanyScopedPrimaryKeyRelatedField
    return True


class CompanyScopedRelationsMixin:
    """Re-scope automatiquement les relations inscriptibles du sérialiseur.

    Deux leviers complémentaires :

    * ``serializer_related_field`` — les relations AUTO-CONSTRUITES par
      ``ModelSerializer`` depuis ``Meta.fields`` naissent déjà scopées ;
    * ``get_fields()`` — les relations DÉCLARÉES à la main
      (``x = serializers.PrimaryKeyRelatedField(queryset=...)``) sont promues
      via :func:`scope_related_field`.

    Seules les relations dont le modèle cible porte ``company`` sont touchées ;
    ``company_scoped_relations_exclude`` permet d'exempter nommément un champ
    (cas rare et documenté : une relation VOLONTAIREMENT inter-société, comme un
    référentiel global).
    """

    serializer_related_field = CompanyScopedPrimaryKeyRelatedField

    #: Noms de champs à NE PAS re-scoper (exemption nommée, à documenter).
    company_scoped_relations_exclude: tuple = ()

    def get_fields(self):
        fields = super().get_fields()
        exclude = set(self.company_scoped_relations_exclude or ())
        for name, field in fields.items():
            if name in exclude:
                continue
            scope_related_field(field)
        return fields


class CompanyScopedModelSerializer(CompanyScopedRelationsMixin,
                                   serializers.ModelSerializer):
    """``ModelSerializer`` dont toutes les relations sont scopées société.

    Base OPTIONNELLE (CRX12) : un sérialiseur existant peut soit en hériter,
    soit poser le mixin, soit n'utiliser que
    :class:`CompanyScopedPrimaryKeyRelatedField` champ par champ. Les trois
    voies donnent la même garantie ; le choix dépend du volume de relations.
    """


class ScheduledJobSerializer(serializers.Serializer):
    """Job planifié normalisé (cf. ``core.jobs.list_jobs``)."""
    name = serializers.CharField()
    task = serializers.CharField()
    schedule = serializers.CharField(allow_blank=True)
    enabled = serializers.BooleanField()
    source = serializers.CharField()
    last_run = serializers.CharField(allow_null=True, required=False)


class WorkflowTemplateStepSerializer(serializers.Serializer):
    """Étape d'un modèle de workflow (FG369, lecture seule)."""
    ordre = serializers.IntegerField()
    nom = serializers.CharField()
    type_approbation = serializers.CharField()
    sla_heures = serializers.IntegerField(allow_null=True)
    role_requis = serializers.CharField(allow_blank=True)
    escalade_vers = serializers.CharField(allow_blank=True)


class WorkflowTemplateSerializer(serializers.Serializer):
    """Modèle de workflow installable (FG369, catalogue — lecture seule)."""
    code = serializers.CharField()
    nom = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    nb_etapes = serializers.IntegerField()
    steps = WorkflowTemplateStepSerializer(many=True)


class WorkflowStepDefinitionSerializer(serializers.ModelSerializer):
    """WIR51 — étape (modèle) d'un ``WorkflowDefinition``.

    Utilisée à la fois IMBRIQUÉE dans ``WorkflowDefinitionSerializer``
    (``definition`` alors imposée par le parent, jamais lue du corps) et en
    AUTONOME via ``WorkflowStepDefinitionViewSet`` (``definition`` fournie et
    validée company-scope pour interdire l'accroche à une définition d'un
    autre tenant)."""

    class Meta:
        model = WorkflowStepDefinition
        fields = [
            'id', 'definition', 'ordre', 'nom', 'type_approbation',
            'sla_heures', 'role_requis', 'escalade_vers',
        ]
        read_only_fields = ['id']
        extra_kwargs = {'definition': {'required': False}}
        # La contrainte d'unicité (definition, ordre) génère sinon un
        # `UniqueTogetherValidator` qui FORCE `definition` requis au niveau
        # champ (ignorant `required: False`, erreur `code='required'`) — ce qui
        # cassait la création IMBRIQUÉE où le parent impose `definition` via
        # `_sync_steps`. On le retire : l'unicité reste garantie par la
        # contrainte DB + la renumérotation 1..n de `_sync_steps`.
        validators = []

    def validate_definition(self, value):
        request = self.context.get('request')
        if (value is not None and request is not None
                and getattr(request.user, 'company_id', None)
                and value.company_id != request.user.company_id):
            raise serializers.ValidationError(
                'Définition hors de votre société.')
        return value

    def validate(self, attrs):
        # En autonome (viewset des étapes), la définition est obligatoire à la
        # création (une étape sans définition n'a pas de rattachement) ;
        # imbriquée, elle est imposée par le parent (`_sync_steps`). Le viewset
        # autonome pose `require_definition` dans le contexte : signal fiable,
        # contrairement à `self.parent` qui n'est pas toujours lié lors d'une
        # validation imbriquée `many=True`.
        if (self.context.get('require_definition') and self.instance is None
                and not attrs.get('definition')):
            raise serializers.ValidationError(
                {'definition': 'Ce champ est obligatoire.'})
        return attrs


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    """WIR51 — définition de workflow (chaîne d'approbation multi-étapes) +
    ses étapes imbriquées.

    ``company`` n'est JAMAIS lue du corps (imposée côté serveur via
    ``TenantMixin``). ``code`` (identifiant stable, unique par société) est
    DÉRIVÉ du ``nom`` côté serveur et reste en lecture seule. Les étapes sont
    créées / remplacées intégralement depuis la liste imbriquée ``steps``
    (renumérotées 1..n dans l'ordre du tableau)."""

    steps = WorkflowStepDefinitionSerializer(many=True, required=False)

    class Meta:
        model = WorkflowDefinition
        fields = [
            'id', 'code', 'nom', 'description', 'actif', 'steps',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'code', 'created_at', 'updated_at']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        validated_data['code'] = self._derive_code(
            validated_data.get('company'), validated_data.get('nom', ''))
        definition = WorkflowDefinition.objects.create(**validated_data)
        self._sync_steps(definition, steps_data)
        return definition

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        for attr in ('nom', 'description', 'actif'):
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        instance.save()
        # Remplacement intégral des étapes UNIQUEMENT si `steps` est fourni.
        if steps_data is not None:
            instance.steps.all().delete()
            self._sync_steps(instance, steps_data)
        return instance

    @staticmethod
    def _sync_steps(definition, steps_data):
        for i, step in enumerate(steps_data):
            step = dict(step)
            step.pop('definition', None)  # imposée par le parent, jamais du corps
            step.pop('ordre', None)       # renumérotée 1..n (unicité garantie)
            WorkflowStepDefinition.objects.create(
                definition=definition, ordre=i + 1, **step)

    @staticmethod
    def _derive_code(company, nom):
        from django.utils.text import slugify
        base = (slugify(nom) or 'workflow').replace('-', '_')[:60]
        code = base
        n = 2
        while WorkflowDefinition.objects.filter(
                company=company, code=code).exists():
            code = ('%s_%d' % (base, n))[:64]
            n += 1
        return code


class DashboardSerializer(serializers.ModelSerializer):
    """FG381 — dashboard sans-code sauvegardé.

    ``company`` et ``owner`` ne sont JAMAIS lus du corps : ``company`` est
    imposée côté serveur (TenantMixin) et ``owner`` est positionné à
    l'utilisateur courant à la création (voir la vue).
    """
    class Meta:
        model = Dashboard
        fields = [
            'id', 'titre', 'description', 'layout', 'partage', 'owner',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """FG370 — transaction de paiement carte en ligne (CMI / Payzone).

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur). Le statut, la
    référence PSP et l'URL de redirection sont en lecture seule : ils ne
    bougent que via le flux de paiement (``core.payment``), jamais par PATCH
    direct. La cible (facture) est désignée de façon générique par
    ``content_type``/``object_id``.
    """
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'provider', 'montant', 'devise', 'statut', 'external_ref',
            'redirect_url', 'payeur_email', 'content_type', 'object_id',
            'paye_le', 'detail', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'external_ref', 'redirect_url', 'paye_le',
            'detail', 'created_at', 'updated_at',
        ]


class SavedQuerySerializer(serializers.ModelSerializer):
    """FG382 — requête d'analyse ad-hoc sauvegardée.

    ``company`` et ``owner`` ne sont JAMAIS lus du corps (imposés côté serveur).
    """
    class Meta:
        model = SavedQuery
        fields = [
            'id', 'titre', 'dataset', 'spec', 'partage', 'owner',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class ScheduledExportSerializer(serializers.ModelSerializer):
    """FG383 — extrait planifié vers SFTP/S3.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur). Le résultat de
    la dernière exécution est en lecture seule.

    NTDATA30 : ``mode``/``champ_curseur`` sont configurables ;
    ``dernier_curseur`` est posé par le RUNNER et reste en lecture seule (une
    borne saisie à la main ferait sauter des lignes).
    """
    class Meta:
        model = ScheduledExport
        fields = [
            'id', 'titre', 'dataset', 'spec', 'format', 'destination', 'cron',
            'actif', 'mode', 'champ_curseur', 'dernier_curseur',
            'derniere_execution_le', 'dernier_statut',
            'dernier_detail', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'dernier_curseur', 'derniere_execution_le', 'dernier_statut',
            'dernier_detail', 'created_at', 'updated_at',
        ]


class DeletionRecordSerializer(serializers.ModelSerializer):
    """FG388 — entrée de corbeille (lecture seule + restauration via action).

    ``model_label`` expose le type de la cible (app.modele) sans révéler de
    modèle métier côté core.
    """
    model_label = serializers.SerializerMethodField()

    class Meta:
        model = DeletionRecord
        fields = [
            'id', 'label', 'model_label', 'object_id', 'deleted_by',
            'restored_at', 'created_at',
        ]
        read_only_fields = fields

    def get_model_label(self, obj):
        ct = obj.content_type
        return f'{ct.app_label}.{ct.model}' if ct else ''


class ModuleToggleSerializer(serializers.ModelSerializer):
    """FG391 — activation/désactivation d'un module par société.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur).
    """
    class Meta:
        model = ModuleToggle
        fields = ['id', 'module', 'actif', 'raison',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantThemeSerializer(serializers.ModelSerializer):
    """FG392 — thème white-label par société.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur, OneToOne).
    """
    class Meta:
        model = TenantTheme
        fields = [
            'id', 'logo_url', 'couleur_primaire', 'couleur_secondaire',
            'domaine', 'nom_affichage', 'extra', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BrandedTemplateSerializer(serializers.ModelSerializer):
    """FG393 — modèle brandé éditable (PDF/email/WhatsApp).

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur). ``variables``
    expose les placeholders détectés dans le corps (aide à l'éditeur).
    """
    variables = serializers.SerializerMethodField()

    class Meta:
        model = BrandedTemplate
        fields = [
            'id', 'kind', 'code', 'nom', 'sujet', 'corps', 'actif',
            'variables', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'variables', 'created_at', 'updated_at']

    def get_variables(self, obj):
        from .templating import variables_utilisees
        return variables_utilisees(f'{obj.sujet}\n{obj.corps}')


class ConsentRecordSerializer(serializers.ModelSerializer):
    """FG394 — entrée du registre de consentement.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur).
    """
    class Meta:
        model = ConsentRecord
        fields = [
            'id', 'subject_identifier', 'purpose', 'granted', 'source',
            'occurred_at', 'version_texte', 'ip_confirmation',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DataSubjectRequestSerializer(serializers.ModelSerializer):
    """FG394 — demande de personne concernée (accès / effacement).

    ``company`` n'est JAMAIS lu du corps. Le statut et le résultat sont en
    lecture seule : ils ne bougent que via le traitement (``core.dsr``).
    """
    class Meta:
        model = DataSubjectRequest
        fields = [
            'id', 'subject_identifier', 'kind', 'statut', 'resultat',
            'traitee_le', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'resultat', 'traitee_le',
            'created_at', 'updated_at',
        ]


class RegistreTraitementSerializer(serializers.ModelSerializer):
    """XPLT23 — registre des traitements CNDP (loi 09-08).

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur).
    """
    class Meta:
        model = RegistreTraitement
        fields = [
            'id', 'code', 'finalite', 'base_legale', 'categories_donnees',
            'categories_personnes', 'destinataires', 'duree_conservation',
            'numero_recepisse', 'date_recepisse', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BackupRunSerializer(serializers.ModelSerializer):
    """FG395 — opération de sauvegarde/restauration (libre-service).

    ``company`` et ``declenche_par`` ne sont JAMAIS lus du corps (imposés côté
    serveur). Le statut, le manifeste, l'horodatage de fin et le détail sont en
    lecture seule : ils ne bougent que via le runner (``core.backup``).
    """
    class Meta:
        model = BackupRun
        fields = [
            'id', 'kind', 'mode', 'statut', 'datasets', 'cron', 'artifact_ref',
            'object_key', 'bytes_taille',
            'manifest', 'declenche_par', 'termine_le', 'detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'manifest', 'declenche_par', 'termine_le', 'detail',
            'object_key', 'bytes_taille',
            'created_at', 'updated_at',
        ]


class ApiUsagePlanSerializer(serializers.ModelSerializer):
    """FG398 — plan de tarif/quota API d'une société.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur, OneToOne).
    """
    class Meta:
        model = ApiUsagePlan
        fields = [
            'id', 'code', 'quota_par_minute', 'quota_par_jour',
            'quota_par_mois', 'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChangelogEntrySerializer(serializers.ModelSerializer):
    """FG399 — note de version (journal des nouveautés).

    Modèle GLOBAL au produit (pas de portée société). ``lu`` indique si
    l'utilisateur courant a accusé lecture de la note (calculé en contexte).
    """
    lu = serializers.SerializerMethodField()

    class Meta:
        model = ChangelogEntry
        fields = [
            'id', 'titre', 'corps', 'version', 'categorie', 'publie',
            'publie_le', 'lu', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'lu', 'created_at', 'updated_at']

    def get_lu(self, obj):
        lus = (self.context or {}).get('entries_lues')
        if lus is None:
            return False
        return obj.pk in lus


class TenantUsageSnapshotSerializer(serializers.ModelSerializer):
    """NTPLT6 — sortie lecture seule d'un instantané d'usage par tenant."""

    company_nom = serializers.CharField(
        source='company.nom', read_only=True, default=None)

    class Meta:
        model = TenantUsageSnapshot
        fields = [
            'id', 'company', 'company_nom', 'jour', 'lignes_par_table',
            'octets_minio', 'nb_requetes_api', 'nb_taches_celery',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class BackgroundJobSerializer(serializers.ModelSerializer):
    """NTPLT29 — sortie lecture seule d'un job de fond avec progression."""

    class Meta:
        model = BackgroundJob
        fields = [
            'id', 'kind', 'statut', 'progress_pct', 'result_file_key',
            'message_erreur', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class OutboxEventSerializer(serializers.ModelSerializer):
    """NTPLT9/10 — sortie lecture seule d'un événement outbox (superviseur)."""

    class Meta:
        model = OutboxEvent
        fields = [
            'id', 'company', 'event_name', 'event_id', 'payload', 'statut',
            'tentatives', 'prochaine_tentative', 'occurred_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields
