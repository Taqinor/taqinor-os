from django.core.validators import RegexValidator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import (
    MOTIF_SANS_NUL, ChaineStricte, ChampsStrictsSansDecimalMixin,
    DecimalStricte, IdInconnu404Mixin, MotifUrlPublie)
from core.mixins import SameCompanyFKSerializerMixin
from core.unicite import ConflitUnicite

from .models import (
    AclGed, AnnotationDocument, ArchivageLegal, Cabinet, CertificatDestruction,
    ChampSignature, Coffre, DemandeApprobation, DemandeDisposition,
    DemandeDocument, DemandeSignatureDocument, DepotPublic,
    Document, DocumentLien, DocumentTag, DocumentTagAssignment, DocumentVersion,
    ExecutionRegleDossier,
    ExigenceDossier, FavoriGed, Folder, JournalAcces, LegalHold, LotEnvoi,
    ModeleDocument,
    PartageGed, PlanificationDocument, PolitiqueRetention,
    RegleAclMetadonnee, RegleApprobationGed, RegleDossier, RoleSignataire,
    RoutageDocumentaire, QuotaStockage, SignataireDemande, TamponSociete,
    TypeChampSignature, ValidationOcrDocument, VueGedEnregistree,
)
from . import services
from .corps_requete import (
    GroupeConditionsField, SectionsModeleField, arbre_canonique,
    erreurs_groupe_conditions)

#: ADOC26 / api-fuzz-full 24/10 — alias d'ingestion e-mail d'un dossier : vide,
#: ou une lettre/un chiffre puis lettres, chiffres, point, tiret, souligné
#: (normalisé en minuscules). Publié tel quel au schéma (validateur du champ).
MOTIF_ALIAS_EMAIL = r'^([A-Za-z0-9][A-Za-z0-9._-]*)?$'
MESSAGE_ALIAS_EMAIL = (
    "Alias invalide : lettres, chiffres, point, tiret ou souligné uniquement.")
#: Plus grand entier d'une colonne ``integer`` PostgreSQL (clé, rang).
ENTIER_SQL_MAX = 2_147_483_647


class DocumentTagSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                            SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED9 — Tag de la taxonomie documentaire (hiérarchique).

    `company` posée côté serveur. `chemin` expose le chemin lisible depuis la
    racine (« Juridique / Contrats / NDA »). Le parent doit appartenir à la même
    société et ne jamais créer de cycle (garde `services.validate_tag_parent`).
    """
    # ERR-ENF11-FUZZ-GED — libellés lus à travers une relation facultative :
    # `allow_null=True` SANS `default=None`. Sur un PATCH (sérialiseur
    # partiel), DRF saute un champ dont la valeur vient de `default` : la
    # clé disparaissait de la réponse alors que le schéma l'exige. Sans
    # défaut, une relation vide rend `null` (vrai pour les 49 champs de
    # cette forme dans ce module).
    parent_nom = serializers.CharField(
        source='parent.nom', read_only=True, allow_null=True)
    chemin = serializers.SerializerMethodField()
    document_count = serializers.SerializerMethodField()
    # ERR-QAH-GED-TAG-CREATION-SLUG — le formulaire « Nouveau tag » n'envoie
    # que le nom : le slug est FACULTATIF et, absent, dérivé du nom côté
    # serveur (unique par société, suffixe -2, -3… en cas de collision).
    # CI #997 fuzz — le motif publié accepte désormais le slug VIDE (jusqu'ici
    # ``SlugField`` publiait ``^[-a-zA-Z0-9_]+$`` : ``""`` était « invalide »
    # au schéma mais accepté) ; pas de rognage, le motif vaut pour la valeur brute.
    slug = ChaineStricte(
        max_length=110, required=False, allow_blank=True,
        trim_whitespace=False,
        validators=[RegexValidator(
            r'^[-a-zA-Z0-9_]*$', message='Identifiant (slug) invalide.')])

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('parent',)

    class Meta:
        model = DocumentTag
        fields = [
            'id', 'nom', 'slug', 'parent', 'parent_nom', 'chemin',
            'couleur', 'description', 'document_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    @extend_schema_field(OpenApiTypes.STR)
    def get_chemin(self, obj):
        parts = [a.nom for a in reversed(obj.ancetres())] + [obj.nom]
        return ' / '.join(parts)

    @extend_schema_field(OpenApiTypes.INT)
    def get_document_count(self, obj):
        return obj.assignments.count()

    def validate(self, attrs):
        request = self.context.get('request')
        parent = attrs.get('parent', getattr(self.instance, 'parent', None))
        if request is not None and parent is not None \
                and parent.company_id != request.user.company_id:
            raise serializers.ValidationError({'parent': 'Tag parent inconnu.'})
        # api-fuzz-full 24/10 — parent = soi-même / descendant, slug déjà pris :
        # le corps est conforme, c'est l'état de la taxonomie qui s'oppose (409).
        from core.conflit_etat import ConflitEtat
        try:
            services.validate_tag_parent(self.instance, parent)
        except ValueError as exc:
            raise ConflitEtat({'parent': [str(exc)]})
        company_id = (request.user.company_id if request is not None
                      else getattr(self.instance, 'company_id', None))
        slug = attrs.get('slug')
        if slug:
            existe = DocumentTag.objects.filter(company_id=company_id, slug=slug)
            if self.instance is not None:
                existe = existe.exclude(pk=self.instance.pk)
            if existe.exists():
                raise ConflitEtat(
                    {'slug': ['Un tag porte déjà cet identifiant.']})
        elif self.instance is None or 'slug' in attrs:
            nom = attrs.get('nom', getattr(self.instance, 'nom', ''))
            attrs['slug'] = self._slug_unique(company_id, nom)
        return attrs

    def _slug_unique(self, company_id, nom):
        from django.utils.text import slugify
        base = (slugify(nom or '') or 'tag')[:100]
        pris = DocumentTag.objects.filter(company_id=company_id)
        if self.instance is not None:
            pris = pris.exclude(pk=self.instance.pk)
        pris = set(pris.filter(slug__startswith=base)
                   .values_list('slug', flat=True))
        slug, n = base, 2
        while slug in pris:
            slug = f'{base}-{n}'
            n += 1
        return slug


class DocumentTagAssignmentSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                      SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED9 — Application d'un tag à un document. `document` et `tag` doivent
    appartenir à la société courante ; `company`/`created_by` posés serveur."""
    tag_nom = serializers.CharField(source='tag.nom', read_only=True, allow_null=True)
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('document', 'tag')

    class Meta:
        model = DocumentTagAssignment
        fields = [
            'id', 'document', 'document_nom', 'tag', 'tag_nom',
            'created_by', 'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']

    def validate(self, attrs):
        request = self.context.get('request')
        if request is None:
            return attrs
        cid = request.user.company_id
        document = attrs.get('document')
        tag = attrs.get('tag')
        if document is not None and document.company_id != cid:
            raise serializers.ValidationError({'document': 'Document inconnu.'})
        if tag is not None and tag.company_id != cid:
            raise serializers.ValidationError({'tag': 'Tag inconnu.'})
        return attrs


class CoffreSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                       SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED8 — Coffre-fort par employé/client (ACL propriétaire + admin).

    `company` et `created_by` sont posés côté serveur. Le propriétaire est un
    employé (`proprietaire`) OU un client (`client`), jamais les deux ni aucun
    (garde `services.validate_coffre_owner`). Le propriétaire et le client
    doivent appartenir à la société courante.
    """
    proprietaire_nom = serializers.CharField(
        source='proprietaire.username', read_only=True, allow_null=True)
    document_count = serializers.SerializerMethodField()

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('proprietaire', 'client')

    class Meta:
        model = Coffre
        fields = [
            'id', 'nom', 'description', 'proprietaire', 'proprietaire_nom',
            'client', 'document_count', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    @extend_schema_field(OpenApiTypes.INT)
    def get_document_count(self, obj):
        return obj.documents.count()

    def validate(self, attrs):
        request = self.context.get('request')
        proprietaire = attrs.get(
            'proprietaire', getattr(self.instance, 'proprietaire', None))
        client = attrs.get('client', getattr(self.instance, 'client', None))
        try:
            services.validate_coffre_owner(proprietaire, client)
        except ValueError as exc:
            if self.instance is not None:
                # ENF11 (nocturne 15/10) — en MODIFICATION, la règle porte sur
                # le coffre EN PLACE combiné au corps (inexprimable au schéma) :
                # refus d'état, 409. La création garde le 400 publié
                # (COFFRE_PROPRIETAIRE_UNIQUE).
                from core.conflit_etat import ConflitEtat
                raise ConflitEtat({'proprietaire': str(exc)})
            raise serializers.ValidationError({'proprietaire': str(exc)})
        if request is not None:
            cid = request.user.company_id
            if proprietaire is not None and proprietaire.company_id != cid:
                raise serializers.ValidationError(
                    {'proprietaire': 'Employé inconnu.'})
            if client is not None and getattr(client, 'company_id', cid) != cid:
                raise serializers.ValidationError({'client': 'Client inconnu.'})
        return attrs


class CabinetSerializer(ChampsStrictsSansDecimalMixin,
                        serializers.ModelSerializer):
    class Meta:
        model = Cabinet
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = ['id', 'nom', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class FolderSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                       SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    cabinet_nom = serializers.CharField(source='cabinet.nom', read_only=True, allow_null=True)
    parent_nom = serializers.CharField(
        source='parent.nom', read_only=True, allow_null=True)
    # api-fuzz-full 24/10 — la règle de l'alias est PUBLIÉE (motif) et tenue
    # telle quelle (pas de rognage silencieux : l'écran envoie déjà `trim()`) ;
    # un alias déjà pris est un conflit d'état (409), voir validate_alias_email.
    alias_email = ChaineStricte(
        required=False, allow_blank=True, max_length=100,
        trim_whitespace=False,
        validators=[RegexValidator(MOTIF_ALIAS_EMAIL, MESSAGE_ALIAS_EMAIL)])

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('cabinet', 'parent')

    class Meta:
        model = Folder
        # `company` posée côté serveur ; `path` matérialisé côté serveur.
        # ADOC26 — `alias_email` (XGED9) se saisit et se relit : un e-mail
        # adressé à « ged+<alias>@… » est classé dans ce dossier.
        fields = [
            'id', 'cabinet', 'cabinet_nom', 'parent', 'parent_nom',
            'nom', 'alias_email', 'path', 'created_at', 'updated_at',
        ]
        read_only_fields = ['path', 'created_at', 'updated_at']

    def validate_alias_email(self, value):
        """ADOC26 — alias normalisé (minuscules), unique par société. Le motif
        publié (``MOTIF_ALIAS_EMAIL``) a déjà été vérifié par le validateur du
        champ ; un alias déjà pris = 409 (état), plus 400."""
        alias = (value or '').lower()
        if not alias:
            return ''
        if '\n' in alias:  # ``$`` Python tolère un saut de ligne final
            raise serializers.ValidationError(MESSAGE_ALIAS_EMAIL)
        request = self.context.get('request')
        if request is not None:
            qs = Folder.objects.filter(
                company_id=request.user.company_id, alias_email=alias)
            if self.instance is not None and isinstance(self.instance, Folder):
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                from core.conflit_etat import ConflitEtat
                raise ConflitEtat({'alias_email': ['Alias déjà utilisé.']})
        return alias

    def get_fields(self):
        """ADOC21 — à la MISE À JOUR, `parent` et `cabinet` sont en lecture
        seule : un dossier ne se déplace que par l'action `deplacer`
        (`services.move_folder` : cycles refusés, chemins réécrits)."""
        fields = super().get_fields()
        if self.instance is not None and isinstance(self.instance, Folder):
            for nom in ('parent', 'cabinet'):
                if nom in fields:
                    fields[nom].read_only = True
        return fields

    def validate(self, attrs):
        """Cabinet et parent doivent appartenir à la société de l'utilisateur,
        et le parent doit vivre dans le même cabinet."""
        # CI #997 fuzz — hors société ou autre cabinet = objet INEXISTANT pour
        # cette requête : 404 (même corps qu'une FK inconnue), plus 400.
        from rest_framework.exceptions import NotFound
        request = self.context.get('request')
        cabinet = attrs.get('cabinet') or getattr(self.instance, 'cabinet', None)
        parent = attrs.get('parent', getattr(self.instance, 'parent', None))
        if request is not None:
            cid = request.user.company_id
            if cabinet is not None and cabinet.company_id != cid:
                raise NotFound({'cabinet': 'Cabinet inconnu.'})
            if parent is not None and parent.company_id != cid:
                raise NotFound({'parent': 'Dossier parent inconnu.'})
        if parent is not None and cabinet is not None \
                and parent.cabinet_id != cabinet.id:
            raise NotFound(
                {'parent': 'Le parent doit appartenir au même cabinet.'})
        return attrs


class DocumentVersionSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    uploaded_by_nom = serializers.CharField(
        source='uploaded_by.username', read_only=True, allow_null=True)
    # GED15 — si la version est une restauration, `restored_from_version` expose
    # le numéro de version source (lisible, jamais écrit du corps de requête).
    restored_from_version = serializers.IntegerField(
        source='restored_from.version', read_only=True, allow_null=True)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('document',)

    class Meta:
        model = DocumentVersion
        # version / company / restored_from posés côté serveur (services).
        fields = [
            'id', 'document', 'version', 'file_key', 'filename', 'size',
            'mime', 'checksum', 'uploaded_by', 'uploaded_by_nom',
            'restored_from', 'restored_from_version', 'created_at',
        ]
        # ADOC8 — `mime` en lecture seule : jamais déclaré par le client
        # (un text/html déclaré serait servi inline).
        # ADOC23 — `size` en lecture seule : le quota ne lit jamais une
        # taille déclarée par le client.
        # ASEC37 — `file_key`/`checksum` en lecture seule : la clé de stockage
        # est TOUJOURS produite par le serveur (fichier téléversé dans la
        # requête, préfixe société), l'empreinte calculée sur les octets reçus.
        read_only_fields = [
            'version', 'uploaded_by', 'restored_from', 'created_at', 'mime',
            'size', 'file_key', 'checksum']
        # `version` est posé côté serveur (services.add_version). On retire le
        # UniqueTogetherValidator (document, version) auto-généré : il évaluerait
        # version à sa valeur par défaut (1) à chaque POST et rejetterait la 2e
        # version. L'unicité réelle reste garantie par la contrainte DB.
        validators = []

    def validate_document(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Document inconnu.')
        return value


class DocumentSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                         SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    folder_nom = serializers.CharField(source='folder.nom', read_only=True, allow_null=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True)
    version_count = serializers.SerializerMethodField()
    derniere_version = serializers.SerializerMethodField()
    derniere_mime = serializers.SerializerMethodField()
    # ADOC35 — favori de l'utilisateur de la requête (ZGED7, personnel).
    favori = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    # GED16 — état du verrou (lecture seule, posé côté serveur).
    locked_by_nom = serializers.CharField(
        source='locked_by.username', read_only=True, allow_null=True)
    is_locked = serializers.BooleanField(read_only=True)
    # GED17 — cycle de vie documentaire (lecture seule : avancé via l'action
    # `cycle-vie`, jamais muté par un PATCH direct). `transitions_autorisees`
    # liste les statuts atteignables depuis le statut courant (pour l'UI).
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    transitions_autorisees = serializers.ListField(
        child=serializers.CharField(), read_only=True)
    # GED26 — corbeille (soft-delete) : champs de TRAÇABILITÉ en lecture seule.
    # Posés/effacés côté serveur via les actions corbeille ; jamais mutés par un
    # PATCH direct. `est_dans_corbeille` est un drapeau pratique pour l'UI.
    supprime_par_nom = serializers.CharField(
        source='supprime_par.username', read_only=True, allow_null=True)
    est_dans_corbeille = serializers.BooleanField(read_only=True)
    # XGED18 — document-lien (URL externe) : `est_document_lien` en lecture
    # seule (dérivé de `url_externe`) pour que le frontend adapte l'aperçu et
    # désactive les actions fichier sans devoir réimplémenter la règle.
    est_document_lien = serializers.BooleanField(read_only=True)
    # ZGED5 — panneau d'informations : propriétaire + contact assigné.
    proprietaire_nom = serializers.CharField(
        source='proprietaire.username', read_only=True, allow_null=True)
    contact_label = serializers.SerializerMethodField()
    # ZGED9 — verrou d'avertissement (léger, distinct du check-out GED16).
    verrou_avertissement_par_nom = serializers.CharField(
        source='verrou_avertissement_par.username', read_only=True, allow_null=True)
    est_verrouille_avertissement = serializers.BooleanField(read_only=True)
    # ERR-ENF11-FUZZ-GED — ``URLField(blank=True)`` publiait ``format: uri`` :
    # la valeur vide servie pour un document ordinaire violait son propre
    # schéma. Champ texte (vide permis) ; l'URL non vide reste validée.
    # CI #997 : le motif http(s) est PUBLIÉ (le fuzz envoyait 2000 « 0 » conformes
    # au schéma, refusés « URL invalide ») ; l'acceptation reste celle de
    # ``URLValidator`` (validate_url_externe), le motif n'est qu'un sous-ensemble.
    url_externe = ChaineStricte(
        max_length=2000, required=False, allow_blank=True,
        validators=[MotifUrlPublie()])

    # CI #997 fuzz — métadonnées typées : un OBJET (le schéma le disait libre,
    # ``[null, null]`` était « conforme » puis refusé « Format invalide »).
    custom_data = serializers.DictField(required=False)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('folder', 'coffre')

    class Meta:
        model = Document
        # `company` + `created_by` posés côté serveur.
        fields = [
            'id', 'reference', 'folder', 'folder_nom', 'coffre', 'nom',
            'description',
            'custom_data', 'created_by', 'created_by_nom', 'version_count',
            'derniere_version', 'derniere_mime', 'favori', 'tags',
            'locked_by', 'locked_by_nom', 'locked_at', 'is_locked',
            'statut', 'statut_display', 'transitions_autorisees',
            # GED21 — contrôle de diffusion (filigrane à la diffusion).
            'watermark_diffusion',
            # GED26 — corbeille (soft-delete).
            'supprime_le', 'supprime_par', 'supprime_par_nom',
            'est_dans_corbeille',
            # XGED18 — document-lien.
            'url_externe', 'est_document_lien',
            # ZGED5 — propriétaire + contact assigné (réassignables via
            # l'action `assigner`, jamais un PATCH direct sur `proprietaire`).
            'proprietaire', 'proprietaire_nom', 'contact_id', 'contact_label',
            # ZGED9 — verrou d'avertissement (posé/levé via les actions
            # dédiées, jamais un PATCH direct).
            'verrou_avertissement_par', 'verrou_avertissement_par_nom',
            'verrou_avertissement_le', 'verrou_avertissement_motif',
            'est_verrouille_avertissement',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'reference', 'created_by', 'created_at', 'updated_at',
            'locked_by', 'locked_at', 'is_locked',
            'statut', 'transitions_autorisees',
            'supprime_le', 'supprime_par', 'est_dans_corbeille',
            'est_document_lien',
            'proprietaire', 'contact_id',
            'verrou_avertissement_par', 'verrou_avertissement_le',
            'verrou_avertissement_motif', 'est_verrouille_avertissement',
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_contact_label(self, obj):
        if not obj.contact_id:
            return None
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return None
        from apps.crm.selectors import client_label
        return client_label(company, obj.contact_id)

    @extend_schema_field(OpenApiTypes.INT)
    def get_version_count(self, obj):
        # APRF36 — annotation posée par DocumentViewSet.get_queryset ; repli
        # hors liste (action, service) = une lecture.
        annote = getattr(obj, 'nb_versions_annote', None)
        if annote is not None:
            return annote
        return obj.versions.count()

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_derniere_version(self, obj):
        if hasattr(obj, 'derniere_version_annotee'):
            return obj.derniere_version_annotee
        last = obj.versions.order_by('-version').first()
        return last.version if last else None

    def get_favori(self, obj) -> bool:
        """ADOC35 — True si l'utilisateur de la requête a mis ce document en
        favori. Lit l'annotation `favori_utilisateur` posée par
        DocumentViewSet (sans N+1) ; à défaut, une requête Exists."""
        annote = getattr(obj, 'favori_utilisateur', None)
        if annote is not None:
            return bool(annote)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        return FavoriGed.objects.filter(
            utilisateur=user, document_id=obj.pk).exists()

    def get_derniere_mime(self, obj) -> str | None:
        """ADOC22 — mime de la version en vigueur (l'écran ne propose les
        opérations PDF — fusion — que pour des PDF)."""
        if hasattr(obj, 'derniere_mime_annotee'):
            return obj.derniere_mime_annotee
        last = obj.versions.order_by('-version').first()
        return last.mime if last else None

    @extend_schema_field({
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'nom': {'type': 'string'},
                'slug': {'type': 'string'},
            },
            'required': ['id', 'nom', 'slug'],
        },
    })
    def get_tags(self, obj):
        # GED9 — tags de la taxonomie appliqués au document (id + nom).
        # APRF36 — lit le préchargement de la liste (`tag_assignments__tag`) ;
        # hors liste, `.all()` repasse par la base avec le tag joint.
        prefetched = 'tag_assignments' in getattr(
            obj, '_prefetched_objects_cache', {})
        assignments = (obj.tag_assignments.all() if prefetched
                       else obj.tag_assignments.select_related('tag').all())
        return [
            {'id': a.tag_id, 'nom': a.tag.nom, 'slug': a.tag.slug}
            for a in assignments
        ]

    def validate_url_externe(self, value):
        if value:
            from django.core.exceptions import ValidationError as DjangoVE
            from django.core.validators import URLValidator
            try:
                URLValidator()(value)
            except DjangoVE:
                raise serializers.ValidationError('URL invalide.')
        return value

    def validate_folder(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Dossier inconnu.')
        return value

    def validate_coffre(self, value):
        """GED8 — Le coffre cible doit appartenir à la société courante ET être
        accessible à l'utilisateur (propriétaire ou admin) — on ne dépose jamais
        un document dans le coffre d'autrui."""
        if value is None:
            return value
        request = self.context.get('request')
        if request is not None:
            if value.company_id != request.user.company_id:
                raise serializers.ValidationError('Coffre-fort inconnu.')
            if not value.is_accessible_by(request.user):
                raise serializers.ValidationError('Coffre-fort inaccessible.')
        return value

    def validate_custom_data(self, value):
        """GED10 — Valide les métadonnées typées contre les définitions actives
        du module « document » de la société (réutilise `customfields`).

        Renvoie le dict nettoyé (clés connues uniquement) ; lève une erreur si un
        champ obligatoire manque ou si un type est incohérent. Hors requête (cas
        des écritures de service) on laisse passer tel quel."""
        request = self.context.get('request')
        if request is None:
            return value
        from apps.customfields.serializers import validate_custom_data
        return validate_custom_data('document', request.user.company, value)


class DocumentLienSerializer(ChampsStrictsSansDecimalMixin,
                             serializers.ModelSerializer):
    """GED6 — Lien polymorphe Document ↔ objet métier.

    En lecture, expose la cible de façon lisible (`target_model` = "ventes.devis",
    `target_label` = nom/référence). `document`, `target_model` et `target_id`
    (la cible) sont posés/validés côté serveur dans la vue — pas dans le corps du
    serializer — comme pour les autres modèles polymorphes du dépôt.
    """
    document_nom = serializers.CharField(source='document.nom', read_only=True, allow_null=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True)
    target_model = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(source='object_id', read_only=True)
    target_label = serializers.SerializerMethodField()

    class Meta:
        model = DocumentLien
        fields = [
            'id', 'document', 'document_nom', 'target_model', 'target_id',
            'target_label', 'created_by', 'created_by_nom', 'created_at',
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_target_model(self, obj):
        ct = obj.content_type
        return f'{ct.app_label}.{ct.model}'

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_target_label(self, obj):
        target = obj.content_object
        if target is None:
            return None
        for attr in ('nom', 'reference', 'numero', 'titre'):
            val = getattr(target, attr, None)
            if val:
                if attr == 'nom':
                    prenom = getattr(target, 'prenom', '') or ''
                    return f'{val} {prenom}'.strip()
                return str(val)
        return str(target)


class DemandeApprobationSerializer(ChampsStrictsSansDecimalMixin,
                                   SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED18 — Demande d'approbation / revue d'un document.

    Lecture seule pour l'essentiel : la demande est créée et décidée via les
    actions/services dédiés (jamais par un POST/PATCH brut), qui posent
    `company`, `demandeur`, `approbateur`, `statut` et `decision_le` côté
    serveur. `document` et `commentaire` sont les seuls champs réellement
    saisissables (la création passe par l'action `documents/<id>/demander-revue`,
    où `document` est borné à la société courante).
    """
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)
    demandeur_nom = serializers.CharField(
        source='demandeur.username', read_only=True, allow_null=True)
    approbateur_nom = serializers.CharField(
        source='approbateur.username', read_only=True, allow_null=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    document_statut = serializers.CharField(
        source='document.statut', read_only=True, allow_null=True)
    is_pending = serializers.BooleanField(read_only=True)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('document',)

    class Meta:
        model = DemandeApprobation
        fields = [
            'id', 'document', 'document_nom', 'document_statut',
            'demandeur', 'demandeur_nom', 'approbateur', 'approbateur_nom',
            'statut', 'statut_display', 'commentaire', 'is_pending',
            'decision_le', 'version', 'created_at', 'updated_at',
        ]
        # ADOC14 — `version` (version relue) posée côté serveur.
        read_only_fields = [
            'demandeur', 'approbateur', 'statut', 'decision_le', 'version',
            'created_at', 'updated_at',
        ]


class PartageGedSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                           serializers.ModelSerializer):
    """GED20 — Partage public d'un document par lien tokenisé.

    Côté GESTION (création/révocation), tout est company-scopé : `company` et
    `created_by` sont posés côté serveur (jamais lus du corps), et `document`
    est borné à la société courante (`validate_document`). Le `token` est
    généré côté serveur et n'est jamais accepté en entrée.

    Le mot de passe est saisi via le champ `password` (write-only) et n'est
    JAMAIS renvoyé en clair : seul `has_password` (booléen) est exposé. Le
    `password_hash` stocké reste interne (jamais sérialisé). `public_url` donne
    le chemin public à partager (le jeton EST le secret d'accès).
    """
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True)
    # Mot de passe en clair, write-only : sert UNIQUEMENT à poser le hash.
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={'input_type': 'password'})
    has_password = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    quota_exhausted = serializers.BooleanField(read_only=True)
    is_accessible = serializers.BooleanField(read_only=True)
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = PartageGed
        fields = [
            'id', 'document', 'document_nom', 'token', 'public_url',
            'expires_at', 'password', 'has_password', 'quota_max',
            'telechargements', 'quota_exhausted', 'is_expired', 'is_accessible',
            # GED21 — filigrane ce lien public (contrôle de diffusion).
            'watermark',
            'actif', 'created_by', 'created_by_nom', 'created_at', 'updated_at',
        ]
        # ADOC6 — `actif` en lecture seule : la révocation passe par
        # /revoquer/ seulement (aucune réactivation par PATCH).
        read_only_fields = [
            'token', 'telechargements', 'created_by', 'actif',
            'created_at', 'updated_at',
        ]

    def get_fields(self):
        """ADOC6 — `document` borné aux documents VISIBLES de l'appelant
        (id invisible = id absent) et non modifiable après création."""
        fields = super().get_fields()
        request = self.context.get('request')
        champ = fields.get('document')
        user = getattr(request, 'user', None)
        if champ is not None and user is not None and user.is_authenticated:
            from . import selectors
            champ.queryset = selectors.documents_visible_to_user(user)
            if self.instance is not None:
                champ.read_only = True
        return fields

    def _voit_le_secret(self, obj):
        """ADOC6 — le jeton (le secret d'accès) n'est montré qu'au créateur
        du partage et à l'administrateur."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser or getattr(user, 'is_admin_role', False):
            return True
        return obj.created_by_id is not None and obj.created_by_id == user.id

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._voit_le_secret(instance):
            data.pop('token', None)
            data.pop('public_url', None)
        return data

    @extend_schema_field(OpenApiTypes.STR)
    def get_public_url(self, obj):
        # Chemin public (relatif) — le jeton EST le secret d'accès.
        return f'/api/django/ged/public/{obj.token}/'

    def validate_document(self, value):
        """Le document doit appartenir à la société courante — on ne partage
        jamais le document d'un autre locataire."""
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Document inconnu.')
        return value

    def _apply_password(self, instance, validated_data):
        """Pose/retire le mot de passe (haché) si `password` est fourni."""
        if 'password' in validated_data:
            raw = validated_data.pop('password')
            instance.set_password(raw)
        return instance

    def create(self, validated_data):
        raw_password = validated_data.pop('password', None)
        instance = PartageGed(**validated_data)
        if raw_password is not None:
            instance.set_password(raw_password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        # `password` fourni (même vide) → (re)pose/retire le hash explicitement.
        if 'password' in validated_data:
            instance.set_password(validated_data.pop('password'))
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance


class PolitiqueRetentionSerializer(ChampsStrictsSansDecimalMixin,
                                   SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED22 — Politique de rétention documentaire (durée + action à l'échéance).

    `company` et `created_by` sont posés côté serveur (jamais lus du corps de
    requête). Les cibles optionnelles `cabinet`/`folder` sont bornées à la
    société courante et mutuellement exclusives (validées ci-dessous). L'action
    par défaut est « signaler » (consultatif) ; aucune suppression automatique
    n'est jamais déclenchée par une politique."""
    scope = serializers.CharField(read_only=True)
    is_destructive = serializers.BooleanField(read_only=True)
    cabinet_nom = serializers.CharField(
        source='cabinet.nom', read_only=True, allow_null=True)
    folder_nom = serializers.CharField(
        source='folder.nom', read_only=True, allow_null=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('cabinet', 'folder')

    class Meta:
        model = PolitiqueRetention
        fields = [
            'id', 'nom', 'description',
            'cabinet', 'cabinet_nom', 'folder', 'folder_nom',
            'type_document', 'duree_conservation_jours', 'action_echeance',
            'scope', 'is_destructive', 'actif',
            'created_by', 'created_by_nom', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
        ]
        # ERR-ENF11-FUZZ-GED : la durée est strictement positive — le schéma
        # publie ``minimum: 1`` (``0`` était « conforme » puis refusé).
        extra_kwargs = {'duree_conservation_jours': {'min_value': 1}}

    def _company_id(self):
        request = self.context.get('request')
        return getattr(getattr(request, 'user', None), 'company_id', None)

    def validate_cabinet(self, value):
        if value is not None and value.company_id != self._company_id():
            raise serializers.ValidationError('Cabinet inconnu.')
        return value

    def validate_folder(self, value):
        if value is not None and value.company_id != self._company_id():
            raise serializers.ValidationError('Dossier inconnu.')
        return value

    def validate_duree_conservation_jours(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                'La durée de conservation doit être strictement positive.')
        return value

    def validate(self, attrs):
        cabinet = attrs.get(
            'cabinet', getattr(self.instance, 'cabinet', None))
        folder = attrs.get('folder', getattr(self.instance, 'folder', None))
        if cabinet is not None and folder is not None:
            raise serializers.ValidationError(
                'Une politique cible au plus un cabinet OU un dossier.')
        return attrs


class ArchivageLegalSerializer(ChampsStrictsSansDecimalMixin,
                               SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED23 — Archivage légal à valeur probante (write-once / object-lock).

    En CRÉATION : seul `document` (et `motif`/`retain_until` optionnels) est lu
    du corps — `company`, `archive_par`, `version`, `hash_integrite` et le verrou
    objet sont posés CÔTÉ SERVEUR via `services.archiver_legalement` (jamais lus
    du corps). En LECTURE : expose la trace immuable complète. Un archivage ne se
    modifie ni ne se supprime jamais (immuable) ; tous les champs effectifs sont
    en lecture seule ici (la création passe par le service / l'action dédiée)."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)
    archive_par_nom = serializers.CharField(
        source='archive_par.username', read_only=True, allow_null=True)
    version_numero = serializers.IntegerField(
        source='version.version', read_only=True, allow_null=True)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('document',)

    class Meta:
        model = ArchivageLegal
        fields = [
            'id', 'document', 'document_nom',
            'version', 'version_numero',
            'archive_le', 'archive_par', 'archive_par_nom',
            'motif', 'hash_integrite',
            'object_lock_retain_until', 'object_lock_applique',
        ]
        read_only_fields = [
            'version', 'archive_le', 'archive_par',
            'hash_integrite', 'object_lock_applique',
        ]


class LegalHoldSerializer(ChampsStrictsSansDecimalMixin,
                          SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED24 — Rétention légale / legal hold (gel anti-suppression).

    En CRÉATION : seuls `document` (et `motif` optionnel) sont lus du corps —
    `company` et `place_par` sont posés CÔTÉ SERVEUR via
    `services.placer_legal_hold` (jamais lus du corps). En LECTURE : expose la
    trace complète (qui a posé/levé, quand, état). La pose/levée passe par les
    actions dédiées (`placer`/`lever`) ou le viewset ; tous les champs d'état
    (`actif`, `date_pose`, `place_par`, `date_levee`, `leve_par`) sont en
    lecture seule ici."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)
    place_par_nom = serializers.CharField(
        source='place_par.username', read_only=True, allow_null=True)
    leve_par_nom = serializers.CharField(
        source='leve_par.username', read_only=True, allow_null=True)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('document',)

    class Meta:
        model = LegalHold
        fields = [
            'id', 'document', 'document_nom',
            'motif', 'actif',
            'date_pose', 'place_par', 'place_par_nom',
            'date_levee', 'leve_par', 'leve_par_nom',
        ]
        read_only_fields = [
            'actif', 'date_pose', 'place_par',
            'date_levee', 'leve_par',
        ]


class DemandeSignatureDocumentSerializer(ChampsStrictsSansDecimalMixin,
                                         SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """GED30 — Demande de signature électronique (point d'intégration + stub no-op).

    En CRÉATION : seuls `document`, `signataire_nom` et `signataire_email` sont
    lus du corps — `company` et `created_by` sont posés CÔTÉ SERVEUR via
    `services.demander_signature` (jamais lus du corps). Tous les champs d'état
    (`statut`, `provider`, `provider_ref`, `date_demande`, `date_signature`) sont
    en LECTURE SEULE : ils évoluent via le service / l'action `marquer-signe`
    (webhook/manuel), jamais par mutation directe de l'API. Couche distincte de
    la signature des contrats (CONTRAT16) et du funnel `STAGES.py`."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True)

    signataires = serializers.SerializerMethodField()
    # ADOC63 — lien ABSOLU de la cérémonie (« Copier le lien de signature »).
    # Mono : jeton de la demande ; circuit multi : None (chaque destinataire a
    # SON lien, exposé sur `signataires[].lien_signature`).
    lien_signature = serializers.SerializerMethodField()

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('document',)

    class Meta:
        model = DemandeSignatureDocument
        fields = [
            'id', 'document', 'document_nom',
            'signataire_nom', 'signataire_email',
            'statut', 'provider', 'provider_ref',
            'date_demande', 'date_signature',
            # XGED1 — lien public + preuves de cérémonie : TOUS en lecture
            # seule via l'API (posés côté serveur uniquement, jamais mutés par
            # une requête authentifiée après coup).
            'token', 'lien_signature', 'expires_at', 'consentement_explicite',
            'adresse_ip', 'user_agent', 'hash_contenu',
            'signature_texte', 'signature_tracee',
            'motif_refus', 'refuse_le',
            # XGED2 — circuit multi-signataires.
            'routage', 'relance_cadence_jours', 'annule_le', 'annule_par',
            'signataires',
            # ZGED14 — traçabilité anti-doublon des notifications émetteur
            # (posée/réarmée par le sweep/`prolonger`, jamais mutée par un
            # PATCH direct).
            'emetteur_notifie_expiration_le',
            # ADOC68 — PDF signé figé (posé une seule fois à la complétion).
            'version_signee',
            'created_by', 'created_by_nom', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'statut', 'provider', 'provider_ref',
            'date_demande', 'date_signature',
            'token', 'consentement_explicite',
            'adresse_ip', 'user_agent', 'hash_contenu',
            'signature_texte', 'signature_tracee',
            'motif_refus', 'refuse_le',
            'annule_le', 'annule_par',
            'emetteur_notifie_expiration_le',
            'version_signee',
            'created_by', 'created_at', 'updated_at',
        ]

    @extend_schema_field(serializers.ListField(
        child=serializers.DictField()))
    def get_signataires(self, obj):
        return SignataireDemandeSerializer(
            obj.signataires.all(), many=True, context=self.context).data

    def get_lien_signature(self, obj) -> str | None:
        if obj.signataires.exists():
            return None
        return services.url_publique_signature(
            obj.token, 'demande', request=self.context.get('request')) or None


class ChampSignatureSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                               SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED3 — Champ positionné sur le PDF à signer (demande OU modèle,
    exactement l'un des deux). `company` posée CÔTÉ SERVEUR (jamais lue du
    corps). `valeur` reste modifiable par cette API de GESTION (édition d'un
    placement) — le remplissage PUBLIC passe par `services.
    enregistrer_valeurs_champs`, jamais par cette route authentifiée.

    ZGED4 — `type_champ_ref` référence optionnellement un `TypeChampSignature`
    du catalogue personnalisé ; `type_champ_ref_detail` expose mode/largeur/
    hauteur/placeholder/astuce pour le rendu public sans requête supplémentaire.
    """
    type_champ_ref_detail = serializers.SerializerMethodField()

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('demande', 'modele', 'type_champ_ref')

    class Meta:
        model = ChampSignature
        fields = [
            'id', 'demande', 'modele', 'type_champ', 'type_champ_ref',
            'type_champ_ref_detail', 'page',
            'x', 'y', 'largeur', 'hauteur', 'role', 'requis', 'valeur',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_type_champ_ref_detail(self, obj):
        t = obj.type_champ_ref
        if t is None:
            return None
        return {
            'id': t.pk, 'code': t.code, 'libelle': t.libelle,
            'mode_saisie': t.mode_saisie,
            'largeur_defaut': str(t.largeur_defaut),
            'hauteur_defaut': str(t.hauteur_defaut),
            'placeholder': t.placeholder, 'astuce': t.astuce,
            'options': t.options, 'auto_remplir': t.auto_remplir,
            'lecture_seule': t.lecture_seule,
        }

    def validate(self, attrs):
        demande = attrs.get('demande', getattr(self.instance, 'demande', None))
        modele = attrs.get('modele', getattr(self.instance, 'modele', None))
        if bool(demande) == bool(modele):
            _refus_cible(
                self, ('demande', 'modele'),
                "Un champ cible exactement une demande OU un modèle de document.")
        request = self.context.get('request')
        if request is not None:
            company = request.user.company
            if demande is not None and demande.company_id != company.id:
                raise serializers.ValidationError(
                    {'demande': 'Demande inconnue.'})
            if modele is not None and modele.company_id != company.id:
                raise serializers.ValidationError(
                    {'modele': 'Modèle inconnu.'})
            type_champ_ref = attrs.get(
                'type_champ_ref', getattr(self.instance, 'type_champ_ref', None))
            if type_champ_ref is not None and type_champ_ref.company_id != company.id:
                raise serializers.ValidationError(
                    {'type_champ_ref': 'Type de champ inconnu.'})
        return attrs


class TypeChampSignatureSerializer(ChampsStrictsSansDecimalMixin,
                                   serializers.ModelSerializer):
    """ZGED4 — Type de champ de signature personnalisé (catalogue éditable).

    `company`/`created_by` posés côté serveur. `code` unique par société
    (garde base + validation applicative pour un message FR clair)."""
    # CI #997 fuzz — décimaux transportés en CHAÎNE (comme le schéma le dit) :
    # un nombre JSON était converti en silence. Aucun écran ne les écrit.
    largeur_defaut = DecimalStricte(
        max_digits=5, decimal_places=2, required=False)
    hauteur_defaut = DecimalStricte(
        max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = TypeChampSignature
        fields = [
            'id', 'code', 'libelle', 'mode_saisie', 'largeur_defaut',
            'hauteur_defaut', 'placeholder', 'astuce', 'options',
            'auto_remplir', 'lecture_seule', 'actif',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate_code(self, value):
        request = self.context.get('request')
        if request is not None:
            company = request.user.company
            qs = TypeChampSignature.objects.filter(company=company, code=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                # ERR-ENF11-FUZZ-GED : doublon = conflit d'état, 409.
                raise ConflitUnicite(
                    "Un type de champ avec ce code existe déjà pour cette société.",
                    champs=['code'])
        return value


class RoutageDocumentaireSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                    SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """ZGED6 — Réglage de centralisation des fichiers d'un autre module.

    `company`/`created_by` posés côté serveur. `source` unique par société
    (garde base + message FR clair). ADOC1 — cabinet, dossier et tags par
    défaut bornés à la société de la requête (id d'ailleurs = id absent)."""
    same_company_fields = ('cabinet_cible', 'dossier_cible', 'tags_defaut')
    cabinet_cible_nom = serializers.CharField(
        source='cabinet_cible.nom', read_only=True, allow_null=True)

    class Meta:
        model = RoutageDocumentaire
        fields = [
            'id', 'source', 'cabinet_cible', 'cabinet_cible_nom',
            'dossier_cible', 'tags_defaut', 'actif',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        # CI #997 api-fuzz : ``tags_defaut`` = ``{}`` passait pour une liste
        # vide (``ManyRelatedField`` accepte tout itérable) alors que le
        # schéma déclare un tableau → 400 nommé pour tout JSON non-liste.
        if (hasattr(data, 'get') and not hasattr(data, 'getlist')
                and data.get('tags_defaut') is not None
                and not isinstance(data.get('tags_defaut'), list)):
            raise serializers.ValidationError(
                {'tags_defaut': "Une liste d'identifiants est attendue."})
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context.get('request')
        cabinet = attrs.get(
            'cabinet_cible', getattr(self.instance, 'cabinet_cible', None))
        if request is not None and cabinet is not None:
            if cabinet.company_id != request.user.company_id:
                raise serializers.ValidationError(
                    {'cabinet_cible': 'Cabinet inconnu.'})
        return attrs

    def validate_source(self, value):
        request = self.context.get('request')
        if request is not None:
            company = request.user.company
            qs = RoutageDocumentaire.objects.filter(company=company, source=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                # ERR-ENF11-FUZZ-GED : doublon = conflit d'état, 409.
                raise ConflitUnicite(
                    "Un routage existe déjà pour cette source dans cette société.",
                    champs=['source'])
        return value


class FavoriGedSerializer(ChampsStrictsSansDecimalMixin,
                          SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """ZGED7 — Favori d'un dossier ou document (personnel, jamais partagé).

    `company`/`utilisateur` posés côté serveur — jamais lus du corps."""
    folder_nom = serializers.CharField(
        source='folder.nom', read_only=True, allow_null=True)
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('folder', 'document')

    class Meta:
        model = FavoriGed
        fields = [
            'id', 'folder', 'folder_nom', 'document', 'document_nom',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def validate(self, attrs):
        folder = attrs.get('folder', getattr(self.instance, 'folder', None))
        document = attrs.get('document', getattr(self.instance, 'document', None))
        if bool(folder) == bool(document):
            raise serializers.ValidationError(
                "Un favori cible exactement un dossier OU un document.")
        request = self.context.get('request')
        if request is not None:
            company = request.user.company
            if folder is not None and folder.company_id != company.id:
                raise serializers.ValidationError({'folder': 'Dossier inconnu.'})
            if document is not None and document.company_id != company.id:
                raise serializers.ValidationError(
                    {'document': 'Document inconnu.'})
        return attrs


class VueGedEnregistreeSerializer(ChampsStrictsSansDecimalMixin,
                                  serializers.ModelSerializer):
    """ZGED8 — Recherche/filtre GED enregistré, partageable.

    `company`/`utilisateur` posés côté serveur — jamais lus du corps."""
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True, allow_null=True)
    est_a_moi = serializers.SerializerMethodField()

    class Meta:
        model = VueGedEnregistree
        fields = [
            'id', 'nom', 'criteres', 'partagee',
            'utilisateur', 'utilisateur_nom', 'est_a_moi',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['utilisateur', 'created_at', 'updated_at']
        # CI #997 fuzz — `criteres` est publié en JSON libre (null compris) :
        # `validate_criteres` lit null comme « aucun critère ».
        extra_kwargs = {'criteres': {'allow_null': True}}

    def validate_criteres(self, valeur):
        return {} if valeur is None else valeur

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_est_a_moi(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return bool(user) and obj.utilisateur_id == user.id


class RoleSignataireSerializer(ChampsStrictsSansDecimalMixin,
                               serializers.ModelSerializer):
    """ZGED1 — Rôle signataire réutilisable (couleur + auth extra + peut
    changer de signataire). `company`/`created_by` posés côté serveur."""
    class Meta:
        model = RoleSignataire
        fields = [
            'id', 'nom', 'couleur', 'auth_extra', 'peut_changer_signataire',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class SignataireDemandeSerializer(ChampsStrictsSansDecimalMixin,
                                  serializers.ModelSerializer):
    """XGED2 — Destinataire (signataire/copie/approbateur) d'une demande de
    signature multi-parties. LECTURE SEULE via l'API — créé/muté uniquement
    par `services` (création groupée, signature/refus par jeton public,
    notifications/relances).

    ZGED1 — `role_signataire` (optionnel) référence le catalogue de rôles
    réutilisables ; `role_couleur`/`role_auth_extra` exposent les valeurs
    HÉRITÉES du rôle référencé pour préremplir l'UI (couleur du champ de
    signature, authentification extra ZGED2)."""
    role_signataire_nom = serializers.CharField(
        source='role_signataire.nom', read_only=True, allow_null=True)
    role_couleur = serializers.CharField(
        source='role_signataire.couleur', read_only=True, allow_null=True)
    role_auth_extra = serializers.CharField(
        source='role_signataire.auth_extra', read_only=True, allow_null=True)
    # ADOC63 — lien ABSOLU de la cérémonie de CE destinataire.
    lien_signature = serializers.SerializerMethodField()

    class Meta:
        model = SignataireDemande
        fields = [
            'id', 'demande', 'nom', 'email', 'telephone', 'ordre', 'role',
            'role_signataire', 'role_signataire_nom', 'role_couleur',
            'role_auth_extra', 'statut', 'notifie_le', 'derniere_relance_le',
            'nb_relances', 'date_action', 'motif_refus', 'lien_signature',
            # ADOC65 — preuves de SA signature (lecture seule).
            'consentement_explicite', 'adresse_ip', 'user_agent',
            'signature_texte', 'signature_tracee', 'hash_contenu',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_lien_signature(self, obj) -> str | None:
        return services.url_publique_signature(
            obj.token, 'signataire',
            request=self.context.get('request')) or None


class ModeleDocumentSerializer(ChampsStrictsSansDecimalMixin,
                               serializers.ModelSerializer):
    """GED27 + GED28 — Modèle de document (fusion/mailing). `company`/`created_by`
    posés CÔTÉ SERVEUR (jamais lus du corps). Le corps HTML porte des jetons
    ``{{ champ }}`` fusionnés au rendu (`services.rendre_modele`). GED28 :
    `cabinet_cible`/`dossier_cible` portent la RÈGLE de classement automatique du
    document généré (le dossier peut être templaté par le contexte de fusion)."""
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True)
    # CI #997 fuzz — `sections` est publié liste d'objets (ou null, lu comme
    # « aucune section » par `validate_sections`), plus en JSON libre.
    sections = SectionsModeleField(required=False, allow_null=True)

    class Meta:
        model = ModeleDocument
        fields = [
            'id', 'nom', 'description', 'categorie', 'corps_html', 'sections',
            'cabinet_cible', 'dossier_cible', 'actif',
            'created_by', 'created_by_nom', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate_sections(self, valeur):
        """NTDOC21 — Valide la STRUCTURE des sections conditionnelles.

        Une section est un objet ``{titre?, corps_html?, conditions?}`` ; son
        arbre de conditions est validé par ``core.rules`` (FG367) AVANT
        persistance — un arbre malformé est refusé ici plutôt que d'être
        silencieusement évalué à False au rendu."""
        if valeur is None:
            return []
        if not isinstance(valeur, list):
            raise serializers.ValidationError(
                "Les sections doivent être une liste d'objets.")
        sortie = []
        for index, section in enumerate(valeur):
            if not isinstance(section, dict):
                raise serializers.ValidationError(
                    f"Section #{index + 1} : un objet est attendu.")
            # api-fuzz-full 24/10 — seules les clés que le rendu lit sont
            # stockées (une clé inconnue portant ``\x00`` faisait refuser le
            # jsonb par PostgreSQL : 500) ; leurs textes sont publiés « sans
            # caractère nul » (``_SectionsModeleSchema``).
            propre = {}
            for cle in ('titre', 'corps_html'):
                if cle in section:
                    texte = section[cle]
                    if not isinstance(texte, str) or '\x00' in texte:
                        raise serializers.ValidationError(
                            f"Section #{index + 1} : « {cle} » doit être un "
                            "texte sans caractère nul.")
                    propre[cle] = texte
            conditions = section.get('conditions', {})
            if conditions != {}:
                erreurs = erreurs_groupe_conditions(conditions)
                if erreurs:
                    raise serializers.ValidationError(
                        f"Section #{index + 1} — conditions invalides : "
                        f"{' ; '.join(erreurs)}")
                conditions = arbre_canonique(conditions)
            if 'conditions' in section:
                propre['conditions'] = conditions
            sortie.append(propre)
        return sortie


class JournalAccesSerializer(ChampsStrictsSansDecimalMixin,
                             serializers.ModelSerializer):
    """GED35 — Entrée d'audit d'accès (LECTURE SEULE).

    Le journal est append-only : il n'est JAMAIS créé/modifié via cette API
    (l'écriture passe par `services.journaliser_acces`, côté serveur, au moment
    d'une lecture). Tous les champs sont en lecture seule."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True, allow_null=True)

    class Meta:
        model = JournalAcces
        fields = [
            'id', 'document', 'document_nom',
            'utilisateur', 'utilisateur_nom',
            'type_acces', 'adresse_ip', 'created_at',
        ]
        read_only_fields = fields


class QuotaStockageSerializer(ChampsStrictsSansDecimalMixin,
                              serializers.ModelSerializer):
    """GED36 — Quota de stockage d'une société.

    `company` est posée CÔTÉ SERVEUR (jamais lue du corps). Expose en lecture
    l'usage courant calculé (`utilise_octets`) et le dépassement éventuel —
    purement informatifs/dérivés, jamais écrits du corps."""
    utilise_octets = serializers.SerializerMethodField()
    depasse = serializers.SerializerMethodField()

    class Meta:
        model = QuotaStockage
        fields = [
            'id', 'quota_octets', 'utilise_octets', 'depasse',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['utilise_octets', 'depasse',
                            'created_at', 'updated_at']

    @extend_schema_field(OpenApiTypes.INT)
    def get_utilise_octets(self, obj):
        return services.usage_stockage_octets(obj.company)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_depasse(self, obj):
        return services.quota_depasse(obj.company)


class DepotPublicSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                            SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED7 — Gestion (côté propriétaire) d'un lien de dépôt public.

    `company`/`created_by`/`token` posés côté serveur. `url_publique` expose le
    chemin de dépôt (le frontend préfixe l'origine). ADOC1 — `folder` borné à
    la société de la requête et non modifiable après création."""
    same_company_fields = ('folder',)
    folder_nom = serializers.CharField(source='folder.nom', read_only=True, allow_null=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_accessible = serializers.BooleanField(read_only=True)

    class Meta:
        model = DepotPublic
        fields = [
            'id', 'folder', 'folder_nom', 'token', 'message', 'expires_at',
            'quota_fichiers', 'quota_octets', 'depots_effectues',
            'octets_deposes', 'actif', 'is_expired', 'is_accessible',
            'created_by', 'created_by_nom', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'token', 'depots_effectues', 'octets_deposes', 'created_by',
            'is_expired', 'is_accessible', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        """ADOC1 — le dossier d'un lien existant ne se déplace plus."""
        attrs = super().validate(attrs)
        if (self.instance is not None and 'folder' in attrs
                and attrs['folder'].pk != self.instance.folder_id):
            raise serializers.ValidationError({
                'folder': ["Le dossier d'un lien de dépôt n'est pas "
                           "modifiable : créez un nouveau lien."]})
        return attrs


class ExigenceDossierSerializer(ChampsStrictsSansDecimalMixin,
                                SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED8 — Modèle de checklist de pièces requises."""
    same_company_fields = ('cabinet', 'folder')

    class Meta:
        model = ExigenceDossier
        fields = [
            'id', 'cabinet', 'folder', 'libelle', 'description',
            'obligatoire', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class DemandeDocumentSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED8 — Demande d'une pièce nommée (interne ou contact externe)."""
    same_company_fields = ('folder', 'exigence', 'utilisateur')
    folder_nom = serializers.CharField(source='folder.nom', read_only=True, allow_null=True)
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True, allow_null=True)

    class Meta:
        model = DemandeDocument
        fields = [
            'id', 'folder', 'folder_nom', 'exigence', 'libelle',
            'utilisateur', 'utilisateur_nom', 'destinataire_nom',
            'destinataire_email', 'echeance', 'statut', 'document',
            'derniere_relance_le', 'nombre_relances',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'statut', 'document', 'derniere_relance_le', 'nombre_relances',
            'created_by', 'created_at', 'updated_at',
        ]


class ValidationOcrDocumentSerializer(ChampsStrictsSansDecimalMixin,
                                      serializers.ModelSerializer):
    """XGED13 — File de validation d'extraction OCR (score de confiance)."""
    document_nom = serializers.CharField(source='document.nom', read_only=True, allow_null=True)
    valide_par_nom = serializers.CharField(
        source='valide_par.username', read_only=True, allow_null=True)

    class Meta:
        model = ValidationOcrDocument
        fields = [
            'id', 'document', 'document_nom', 'score_confiance',
            'champs_extraits', 'valide', 'valide_par', 'valide_par_nom',
            'valide_le', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'document', 'score_confiance', 'valide', 'valide_par',
            'valide_le', 'created_at', 'updated_at',
        ]


class AnnotationDocumentSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                   SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED16 — Annotation/tampon posé sur l'image d'une version (couche
    séparée — n'affecte jamais le fichier original)."""
    same_company_fields = ('version',)
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, allow_null=True)

    class Meta:
        model = AnnotationDocument
        fields = [
            'id', 'version', 'type_annotation', 'page', 'x', 'y', 'contenu',
            'auteur', 'auteur_nom', 'created_at',
        ]
        read_only_fields = ['auteur', 'created_at']


#: XGED19 — types d'action qu'exécute ``services._executer_action_regle``.
TYPES_ACTION_REGLE = (
    'tag', 'deplacer', 'proprietaire', 'demander_approbation',
    'demander_signature')


@extend_schema_field({'nullable': True, 'anyOf': [
    {'type': 'string', 'pattern': MOTIF_SANS_NUL},
    {'type': 'number'}, {'type': 'boolean'}]})
class _ScalaireSansNul(serializers.Field):
    """Valeur d'un paramètre d'action : texte sans caractère nul, nombre,
    booléen ou null (jamais un objet ni une liste)."""

    def __init__(self, **kwargs):
        kwargs.setdefault('allow_null', True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, str) and '\x00' not in data:
            return data
        if isinstance(data, (bool, int, float)):
            return data
        raise serializers.ValidationError(
            'Texte (sans caractère nul), nombre ou booléen attendu.')

    def to_representation(self, value):
        return value


class _ParamsActionRegle(serializers.DictField):
    """``params`` d'une action : objet de scalaires. Une CLÉ portant un
    caractère nul (inexprimable au schéma OpenAPI 3.0, sans
    ``propertyNames``) est un refus d'état : 409, comme ailleurs (ENF11)."""

    def __init__(self, **kwargs):
        kwargs.setdefault('child', _ScalaireSansNul())
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, dict) and any('\x00' in str(k) for k in data):
            from core.conflit_etat import ConflitEtat
            raise ConflitEtat(
                {'actions': ['Clé de paramètre sans caractère nul attendue.']})
        return super().to_internal_value(data)


class ActionRegleDossierSerializer(serializers.Serializer):
    """api-fuzz-full 24/10 — une action de règle de dossier telle que le
    moteur la lit (``type`` + ``params``) : une action « dict libre » portant
    une clé à ``\\x00`` faisait refuser le jsonb par PostgreSQL (500) ; seules
    ces deux clés sont désormais stockées."""
    type = serializers.ChoiceField(choices=TYPES_ACTION_REGLE)
    params = _ParamsActionRegle(required=False)

    def to_representation(self, instance):
        # Lecture : l'action stockée telle quelle (lignes antérieures comprises).
        return dict(instance) if isinstance(instance, dict) else instance


class RegleDossierSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                             SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED19 — Règle d'action automatique à l'upload dans un dossier.

    `condition_group` doit être un groupe `core.rules` valide — validé côté
    vue via `core.rules.validate_condition_group` avant persistance."""
    same_company_fields = ('folder',)
    folder_nom = serializers.CharField(source='folder.nom', read_only=True, allow_null=True)
    condition_group = GroupeConditionsField()  # ERR-ENF11-FUZZ-GED : arbre publié
    # CI #997 api-fuzz : un JSONField publie « n'importe quoi » (null compris) et
    # DRF refuse null — la liste d'étapes est déclarée (liste d'objets).
    actions = serializers.ListField(
        child=ActionRegleDossierSerializer(), required=False)

    class Meta:
        model = RegleDossier
        fields = [
            'id', 'folder', 'folder_nom', 'nom', 'condition_group', 'actions',
            'actif', 'ordre', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class ExecutionRegleDossierSerializer(ChampsStrictsSansDecimalMixin,
                                      serializers.ModelSerializer):
    """PACT132 — Journal d'exécution d'une `RegleDossier` (lecture seule).

    Exposé par l'action `RegleDossierViewSet.executions` — jamais de CRUD
    direct (les lignes sont posées côté serveur par
    `services.appliquer_regles_dossier`)."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)

    class Meta:
        model = ExecutionRegleDossier
        fields = [
            'id', 'regle', 'document', 'document_nom', 'declenchee',
            'resultats', 'created_at',
        ]
        read_only_fields = fields


class RegleApprobationGedSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                    serializers.ModelSerializer):
    """XGED20 — Routage conditionnel des approbations par métadonnées."""
    condition_group = GroupeConditionsField()  # ERR-ENF11-FUZZ-GED : arbre publié
    # CI #997 api-fuzz : chaîne d'ids utilisateur déclarée (jamais null).
    approbateurs = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False)

    class Meta:
        model = RegleApprobationGed
        fields = [
            'id', 'libelle', 'condition_group', 'approbateurs', 'priorite',
            'actif', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


def _refus_cible(serializer, noms, message):
    """ENF11 — refus de la règle « exactement une cible » / « au moins un
    principal ». Le CORPS d'un PATCH qui ne nomme qu'UN des champs liés ne dit
    pas à lui seul si la règle tient : c'est la ligne en base qui tranche → 409
    d'ÉTAT. Dans tous les autres cas la règle se lit dans le corps (publiée au
    schéma) → 400."""
    donnees = getattr(serializer, 'initial_data', None) or {}
    nommes = [n for n in noms if n in donnees]
    if (serializer.instance is not None and serializer.partial
            and 0 < len(nommes) < len(noms)):
        from core.conflit_etat import ConflitEtat
        raise ConflitEtat({'non_field_errors': [message]})
    raise serializers.ValidationError(message)


class AclGedSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                       SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """WIR163 — Droit d'accès GED19 par dossier/document (héritage + override).

    ``company``/``created_by`` posés côté serveur (TenantMixin/ViewSet) —
    jamais lus du corps de requête. La cible (``folder`` XOR ``document``, au
    moins un principal ``utilisateur``/``role``) est re-validée ici — les
    mêmes règles que ``AclGed.clean()`` — pour renvoyer un 400 propre plutôt
    que de laisser la ``CheckConstraint`` base lever une 500 ; la cible doit
    en plus appartenir à la société de l'appelant (jamais de fuite
    cross-société via un id de dossier/document d'une autre société)."""
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True, allow_null=True)
    role_nom = serializers.CharField(
        source='role.nom', read_only=True, allow_null=True)
    # NTPRT13 — principal PORTAIL CLIENT (voir ``AclGed.client``) : exposé ici
    # pour que l'écran interne puisse effectivement poser un partage client
    # (sans ce champ, le modèle le permettait mais aucune API ne l'atteignait).
    client_nom = serializers.CharField(
        source='client.nom', read_only=True, allow_null=True)
    folder_nom = serializers.CharField(
        source='folder.nom', read_only=True, allow_null=True)
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, allow_null=True)
    # Un id de client d'une AUTRE société ne doit jamais devenir un partage :
    # validation même-société du FK écrivable (check_fk_scoping).
    # ADOC36 — cible et principaux bornés à la société de la requête.
    same_company_fields = ('client', 'folder', 'document', 'utilisateur', 'role')

    class Meta:
        model = AclGed
        fields = [
            'id', 'folder', 'folder_nom', 'document', 'document_nom',
            'utilisateur', 'utilisateur_nom', 'role', 'role_nom',
            'client', 'client_nom', 'niveau',
            'herite', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        folder = attrs.get('folder', getattr(self.instance, 'folder', None))
        document = attrs.get(
            'document', getattr(self.instance, 'document', None))
        if bool(folder) == bool(document):
            _refus_cible(
                self, ('folder', 'document'),
                "Une entrée ACL cible exactement un dossier OU un document.")
        utilisateur = attrs.get(
            'utilisateur', getattr(self.instance, 'utilisateur', None))
        role = attrs.get('role', getattr(self.instance, 'role', None))
        # NTPRT13 — un partage PORTAIL CLIENT est un principal valide au même
        # titre qu'un utilisateur ou un rôle (``AclGed.clean()``/contrainte
        # base ``ged_acl_principal_required_v2``).
        client = attrs.get('client', getattr(self.instance, 'client', None))
        if not utilisateur and not role and not client:
            _refus_cible(
                self, ('utilisateur', 'role', 'client'),
                "Une entrée ACL désigne au moins un utilisateur, un rôle ou "
                "un client (portail).")
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        company_id = getattr(user, 'company_id', None) if user else None
        if company_id is not None:
            cible = folder or document
            if getattr(cible, 'company_id', None) != company_id:
                raise serializers.ValidationError(
                    "Le dossier/document ciblé doit appartenir à votre société.")
            # NTPRT13 — un ``client`` d'une AUTRE société ne peut jamais
            # devenir principal (même garde que folder/document ci-dessus).
            if client is not None and client.company_id != company_id:
                raise serializers.ValidationError(
                    "Le client désigné doit appartenir à votre société.")
        return attrs


class TamponSocieteSerializer(ChampsStrictsSansDecimalMixin,
                              serializers.ModelSerializer):
    """WIR164 — Tampon prédéfini PROPRE à la société (XGED16, en plus des 3
    tampons système `TAMPONS_SYSTEME`, jamais modifiables). `company` posée
    côté serveur — jamais lue du corps de requête."""
    class Meta:
        model = TamponSociete
        fields = ['id', 'libelle', 'created_at']
        read_only_fields = ['created_at']


class RegleAclMetadonneeSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                   SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED21 — ACL automatique pilotée par métadonnées (couche dynamique,
    évaluée à chaque lecture par `selectors.acl_effective` — jamais de ligne
    `AclGed` matérialisée)."""
    role_nom = serializers.CharField(
        source='role.nom', read_only=True, allow_null=True)
    condition_group = GroupeConditionsField()  # ERR-ENF11-FUZZ-GED : arbre publié

    # ADOC36 — FK inscriptibles bornées à la société de la requête.
    same_company_fields = ('role',)

    class Meta:
        model = RegleAclMetadonnee
        fields = [
            'id', 'nom', 'condition_group', 'role', 'role_nom', 'niveau',
            'priorite', 'actif', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class CertificatDestructionSerializer(ChampsStrictsSansDecimalMixin,
                                      serializers.ModelSerializer):
    """XGED23 — Certificat immuable de destruction (lecture seule)."""
    detruit_par_nom = serializers.CharField(
        source='detruit_par.username', read_only=True, allow_null=True)

    class Meta:
        model = CertificatDestruction
        fields = [
            'id', 'demande', 'document_id_origine', 'document_nom',
            'politique_appliquee', 'hash_metadonnees', 'detruit_le',
            'detruit_par', 'detruit_par_nom',
        ]
        read_only_fields = fields


class DemandeDispositionSerializer(ChampsStrictsSansDecimalMixin,
                                   serializers.ModelSerializer):
    """XGED23 — Demande de disposition fin de rétention (revue humaine).

    `documents` porte les ids proposés (résolus/filtrés côté serveur à la
    création — jamais lus tels quels sans validation)."""
    demandeur_nom = serializers.CharField(
        source='demandeur.username', read_only=True, allow_null=True)
    approbateur_nom = serializers.CharField(
        source='approbateur.username', read_only=True, allow_null=True)
    certificats = CertificatDestructionSerializer(many=True, read_only=True)

    class Meta:
        model = DemandeDisposition
        fields = [
            'id', 'libelle', 'action', 'documents', 'statut',
            'demandeur', 'demandeur_nom', 'approbateur', 'approbateur_nom',
            'commentaire', 'decision_le', 'executee_le', 'certificats',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'statut', 'demandeur', 'approbateur', 'decision_le',
            'executee_le', 'certificats', 'created_at', 'updated_at',
        ]


class LotEnvoiSerializer(ChampsStrictsSansDecimalMixin,
                         serializers.ModelSerializer):
    """XGED27 — Lot d'envoi en masse de demandes de signature (suivi groupé,
    lecture seule côté API — créé uniquement via l'action dédiée)."""
    modele_nom = serializers.CharField(
        source='modele.nom', read_only=True, allow_null=True)

    class Meta:
        model = LotEnvoi
        fields = [
            'id', 'modele', 'modele_nom', 'libelle', 'resultats', 'total',
            'nb_envoyes', 'nb_vus', 'nb_signes', 'nb_refuses', 'nb_erreurs',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PlanificationDocumentSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                                      SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    """XGED15 — Activité planifiée sur un document (« relancer le J+7 »)."""
    same_company_fields = ('document', 'assigne_a')
    document_nom = serializers.CharField(source='document.nom', read_only=True, allow_null=True)
    assigne_a_nom = serializers.CharField(
        source='assigne_a.username', read_only=True, allow_null=True)

    class Meta:
        model = PlanificationDocument
        fields = [
            'id', 'document', 'document_nom', 'libelle', 'echeance',
            'assigne_a', 'assigne_a_nom', 'faite', 'notifiee',
            'created_by', 'created_at',
        ]
        read_only_fields = ['notifiee', 'created_by', 'created_at']


# ── ADOC76 — validation du corps de creer-multi (400 nommé, jamais 500) ─────

def _codes(model, champ):
    return [code for code, _ in model._meta.get_field(champ).choices]


class DestinataireMultiSerializer(serializers.Serializer):
    """ADOC76 — Un destinataire du circuit : rôle FERMÉ (signataire / copie /
    approbateur), ordre ≥ 1.

    api-fuzz-full 24/10 — textes STRICTS (motif « sans caractère nul » publié :
    un ``nom`` à ``\\x00`` était conforme puis refusé) et entiers bornés à la
    colonne (un ``ordre`` de 38 chiffres débordait l'entier SQL : 500)."""
    nom = ChaineStricte(max_length=255)
    email = serializers.EmailField(required=False, allow_blank=True)
    telephone = ChaineStricte(
        required=False, allow_blank=True, max_length=32)
    role = serializers.ChoiceField(
        choices=_codes(SignataireDemande, 'role'), default='signataire')
    ordre = serializers.IntegerField(
        min_value=1, max_value=ENTIER_SQL_MAX, required=False)
    role_signataire = serializers.IntegerField(
        min_value=1, max_value=ENTIER_SQL_MAX, required=False, allow_null=True)


class CreerMultiSignatairesSerializer(serializers.Serializer):
    """ADOC76 — Corps de `demandes-signature/creer-multi/` : routage parmi
    ses choix, `expires_at` date ISO valide, au moins UN destinataire de rôle
    « signataire » (sans quoi la demande resterait en attente à vie)."""
    document = serializers.IntegerField()
    destinataires = DestinataireMultiSerializer(many=True, allow_empty=False)
    routage = serializers.ChoiceField(
        choices=_codes(DemandeSignatureDocument, 'routage'),
        required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    relance_cadence_jours = serializers.IntegerField(
        min_value=0, required=False, allow_null=True)

    def validate_destinataires(self, value):
        if not any(d.get('role', 'signataire') == 'signataire' for d in value):
            raise serializers.ValidationError(
                "Le circuit doit compter au moins un destinataire de rôle "
                "« signataire ».")
        return value
