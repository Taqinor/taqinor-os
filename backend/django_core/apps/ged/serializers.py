from rest_framework import serializers

from .models import (
    AnnotationDocument, ArchivageLegal, Cabinet, ChampSignature, Coffre,
    DemandeApprobation, DemandeDocument, DemandeSignatureDocument, DepotPublic,
    Document, DocumentLien, DocumentTag, DocumentTagAssignment, DocumentVersion,
    ExigenceDossier, Folder, JournalAcces, LegalHold, ModeleDocument,
    PartageGed, PlanificationDocument, PolitiqueRetention,
    RegleApprobationGed, RegleDossier, QuotaStockage, SignataireDemande,
    ValidationOcrDocument,
)
from . import services


class DocumentTagSerializer(serializers.ModelSerializer):
    """GED9 — Tag de la taxonomie documentaire (hiérarchique).

    `company` posée côté serveur. `chemin` expose le chemin lisible depuis la
    racine (« Juridique / Contrats / NDA »). Le parent doit appartenir à la même
    société et ne jamais créer de cycle (garde `services.validate_tag_parent`).
    """
    parent_nom = serializers.CharField(
        source='parent.nom', read_only=True, default=None)
    chemin = serializers.SerializerMethodField()
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTag
        fields = [
            'id', 'nom', 'slug', 'parent', 'parent_nom', 'chemin',
            'couleur', 'description', 'document_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_chemin(self, obj):
        parts = [a.nom for a in reversed(obj.ancetres())] + [obj.nom]
        return ' / '.join(parts)

    def get_document_count(self, obj):
        return obj.assignments.count()

    def validate(self, attrs):
        request = self.context.get('request')
        parent = attrs.get('parent', getattr(self.instance, 'parent', None))
        if request is not None and parent is not None \
                and parent.company_id != request.user.company_id:
            raise serializers.ValidationError({'parent': 'Tag parent inconnu.'})
        try:
            services.validate_tag_parent(self.instance, parent)
        except ValueError as exc:
            raise serializers.ValidationError({'parent': str(exc)})
        return attrs


class DocumentTagAssignmentSerializer(serializers.ModelSerializer):
    """GED9 — Application d'un tag à un document. `document` et `tag` doivent
    appartenir à la société courante ; `company`/`created_by` posés serveur."""
    tag_nom = serializers.CharField(source='tag.nom', read_only=True)
    document_nom = serializers.CharField(
        source='document.nom', read_only=True)

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


class CoffreSerializer(serializers.ModelSerializer):
    """GED8 — Coffre-fort par employé/client (ACL propriétaire + admin).

    `company` et `created_by` sont posés côté serveur. Le propriétaire est un
    employé (`proprietaire`) OU un client (`client`), jamais les deux ni aucun
    (garde `services.validate_coffre_owner`). Le propriétaire et le client
    doivent appartenir à la société courante.
    """
    proprietaire_nom = serializers.CharField(
        source='proprietaire.username', read_only=True, default=None)
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Coffre
        fields = [
            'id', 'nom', 'description', 'proprietaire', 'proprietaire_nom',
            'client', 'document_count', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

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
            raise serializers.ValidationError({'proprietaire': str(exc)})
        if request is not None:
            cid = request.user.company_id
            if proprietaire is not None and proprietaire.company_id != cid:
                raise serializers.ValidationError(
                    {'proprietaire': 'Employé inconnu.'})
            if client is not None and getattr(client, 'company_id', cid) != cid:
                raise serializers.ValidationError({'client': 'Client inconnu.'})
        return attrs


class CabinetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cabinet
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = ['id', 'nom', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class FolderSerializer(serializers.ModelSerializer):
    cabinet_nom = serializers.CharField(source='cabinet.nom', read_only=True)
    parent_nom = serializers.CharField(
        source='parent.nom', read_only=True, default=None)

    class Meta:
        model = Folder
        # `company` posée côté serveur ; `path` matérialisé côté serveur.
        fields = [
            'id', 'cabinet', 'cabinet_nom', 'parent', 'parent_nom',
            'nom', 'path', 'created_at', 'updated_at',
        ]
        read_only_fields = ['path', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Cabinet et parent doivent appartenir à la société de l'utilisateur,
        et le parent doit vivre dans le même cabinet."""
        request = self.context.get('request')
        cabinet = attrs.get('cabinet') or getattr(self.instance, 'cabinet', None)
        parent = attrs.get('parent', getattr(self.instance, 'parent', None))
        if request is not None:
            cid = request.user.company_id
            if cabinet is not None and cabinet.company_id != cid:
                raise serializers.ValidationError({'cabinet': 'Cabinet inconnu.'})
            if parent is not None and parent.company_id != cid:
                raise serializers.ValidationError({'parent': 'Dossier parent inconnu.'})
        if parent is not None and cabinet is not None \
                and parent.cabinet_id != cabinet.id:
            raise serializers.ValidationError(
                {'parent': 'Le parent doit appartenir au même cabinet.'})
        return attrs


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by_nom = serializers.CharField(
        source='uploaded_by.username', read_only=True, default=None)
    # GED15 — si la version est une restauration, `restored_from_version` expose
    # le numéro de version source (lisible, jamais écrit du corps de requête).
    restored_from_version = serializers.IntegerField(
        source='restored_from.version', read_only=True, default=None)

    class Meta:
        model = DocumentVersion
        # version / company / restored_from posés côté serveur (services).
        fields = [
            'id', 'document', 'version', 'file_key', 'filename', 'size',
            'mime', 'checksum', 'uploaded_by', 'uploaded_by_nom',
            'restored_from', 'restored_from_version', 'created_at',
        ]
        read_only_fields = ['version', 'uploaded_by', 'restored_from', 'created_at']
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


class DocumentSerializer(serializers.ModelSerializer):
    folder_nom = serializers.CharField(source='folder.nom', read_only=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
    version_count = serializers.SerializerMethodField()
    derniere_version = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    # GED16 — état du verrou (lecture seule, posé côté serveur).
    locked_by_nom = serializers.CharField(
        source='locked_by.username', read_only=True, default=None)
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
        source='supprime_par.username', read_only=True, default=None)
    est_dans_corbeille = serializers.BooleanField(read_only=True)
    # XGED18 — document-lien (URL externe) : `est_document_lien` en lecture
    # seule (dérivé de `url_externe`) pour que le frontend adapte l'aperçu et
    # désactive les actions fichier sans devoir réimplémenter la règle.
    est_document_lien = serializers.BooleanField(read_only=True)

    class Meta:
        model = Document
        # `company` + `created_by` posés côté serveur.
        fields = [
            'id', 'folder', 'folder_nom', 'coffre', 'nom', 'description',
            'custom_data', 'created_by', 'created_by_nom', 'version_count',
            'derniere_version', 'tags',
            'locked_by', 'locked_by_nom', 'locked_at', 'is_locked',
            'statut', 'statut_display', 'transitions_autorisees',
            # GED21 — contrôle de diffusion (filigrane à la diffusion).
            'watermark_diffusion',
            # GED26 — corbeille (soft-delete).
            'supprime_le', 'supprime_par', 'supprime_par_nom',
            'est_dans_corbeille',
            # XGED18 — document-lien.
            'url_externe', 'est_document_lien',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'locked_by', 'locked_at', 'is_locked',
            'statut', 'transitions_autorisees',
            'supprime_le', 'supprime_par', 'est_dans_corbeille',
            'est_document_lien',
        ]

    def get_version_count(self, obj):
        return obj.versions.count()

    def get_derniere_version(self, obj):
        last = obj.versions.order_by('-version').first()
        return last.version if last else None

    def get_tags(self, obj):
        # GED9 — tags de la taxonomie appliqués au document (id + nom).
        return [
            {'id': a.tag_id, 'nom': a.tag.nom, 'slug': a.tag.slug}
            for a in obj.tag_assignments.select_related('tag').all()
        ]

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


class DocumentLienSerializer(serializers.ModelSerializer):
    """GED6 — Lien polymorphe Document ↔ objet métier.

    En lecture, expose la cible de façon lisible (`target_model` = "ventes.devis",
    `target_label` = nom/référence). `document`, `target_model` et `target_id`
    (la cible) sont posés/validés côté serveur dans la vue — pas dans le corps du
    serializer — comme pour les autres modèles polymorphes du dépôt.
    """
    document_nom = serializers.CharField(source='document.nom', read_only=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
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

    def get_target_model(self, obj):
        ct = obj.content_type
        return f'{ct.app_label}.{ct.model}'

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


class DemandeApprobationSerializer(serializers.ModelSerializer):
    """GED18 — Demande d'approbation / revue d'un document.

    Lecture seule pour l'essentiel : la demande est créée et décidée via les
    actions/services dédiés (jamais par un POST/PATCH brut), qui posent
    `company`, `demandeur`, `approbateur`, `statut` et `decision_le` côté
    serveur. `document` et `commentaire` sont les seuls champs réellement
    saisissables (la création passe par l'action `documents/<id>/demander-revue`,
    où `document` est borné à la société courante).
    """
    document_nom = serializers.CharField(
        source='document.nom', read_only=True)
    demandeur_nom = serializers.CharField(
        source='demandeur.username', read_only=True, default=None)
    approbateur_nom = serializers.CharField(
        source='approbateur.username', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    document_statut = serializers.CharField(
        source='document.statut', read_only=True)
    is_pending = serializers.BooleanField(read_only=True)

    class Meta:
        model = DemandeApprobation
        fields = [
            'id', 'document', 'document_nom', 'document_statut',
            'demandeur', 'demandeur_nom', 'approbateur', 'approbateur_nom',
            'statut', 'statut_display', 'commentaire', 'is_pending',
            'decision_le', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'demandeur', 'approbateur', 'statut', 'decision_le',
            'created_at', 'updated_at',
        ]


class PartageGedSerializer(serializers.ModelSerializer):
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
        source='document.nom', read_only=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
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
        read_only_fields = [
            'token', 'telechargements', 'created_by',
            'created_at', 'updated_at',
        ]

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


class PolitiqueRetentionSerializer(serializers.ModelSerializer):
    """GED22 — Politique de rétention documentaire (durée + action à l'échéance).

    `company` et `created_by` sont posés côté serveur (jamais lus du corps de
    requête). Les cibles optionnelles `cabinet`/`folder` sont bornées à la
    société courante et mutuellement exclusives (validées ci-dessous). L'action
    par défaut est « signaler » (consultatif) ; aucune suppression automatique
    n'est jamais déclenchée par une politique."""
    scope = serializers.CharField(read_only=True)
    is_destructive = serializers.BooleanField(read_only=True)
    cabinet_nom = serializers.CharField(
        source='cabinet.nom', read_only=True, default=None)
    folder_nom = serializers.CharField(
        source='folder.nom', read_only=True, default=None)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

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


class ArchivageLegalSerializer(serializers.ModelSerializer):
    """GED23 — Archivage légal à valeur probante (write-once / object-lock).

    En CRÉATION : seul `document` (et `motif`/`retain_until` optionnels) est lu
    du corps — `company`, `archive_par`, `version`, `hash_integrite` et le verrou
    objet sont posés CÔTÉ SERVEUR via `services.archiver_legalement` (jamais lus
    du corps). En LECTURE : expose la trace immuable complète. Un archivage ne se
    modifie ni ne se supprime jamais (immuable) ; tous les champs effectifs sont
    en lecture seule ici (la création passe par le service / l'action dédiée)."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, default=None)
    archive_par_nom = serializers.CharField(
        source='archive_par.username', read_only=True, default=None)
    version_numero = serializers.IntegerField(
        source='version.version', read_only=True, default=None)

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


class LegalHoldSerializer(serializers.ModelSerializer):
    """GED24 — Rétention légale / legal hold (gel anti-suppression).

    En CRÉATION : seuls `document` (et `motif` optionnel) sont lus du corps —
    `company` et `place_par` sont posés CÔTÉ SERVEUR via
    `services.placer_legal_hold` (jamais lus du corps). En LECTURE : expose la
    trace complète (qui a posé/levé, quand, état). La pose/levée passe par les
    actions dédiées (`placer`/`lever`) ou le viewset ; tous les champs d'état
    (`actif`, `date_pose`, `place_par`, `date_levee`, `leve_par`) sont en
    lecture seule ici."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, default=None)
    place_par_nom = serializers.CharField(
        source='place_par.username', read_only=True, default=None)
    leve_par_nom = serializers.CharField(
        source='leve_par.username', read_only=True, default=None)

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


class DemandeSignatureDocumentSerializer(serializers.ModelSerializer):
    """GED30 — Demande de signature électronique (point d'intégration + stub no-op).

    En CRÉATION : seuls `document`, `signataire_nom` et `signataire_email` sont
    lus du corps — `company` et `created_by` sont posés CÔTÉ SERVEUR via
    `services.demander_signature` (jamais lus du corps). Tous les champs d'état
    (`statut`, `provider`, `provider_ref`, `date_demande`, `date_signature`) sont
    en LECTURE SEULE : ils évoluent via le service / l'action `marquer-signe`
    (webhook/manuel), jamais par mutation directe de l'API. Couche distincte de
    la signature des contrats (CONTRAT16) et du funnel `STAGES.py`."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, default=None)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    signataires = serializers.SerializerMethodField()

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
            'token', 'expires_at', 'consentement_explicite',
            'adresse_ip', 'user_agent', 'hash_contenu',
            'signature_texte', 'signature_tracee',
            'motif_refus', 'refuse_le',
            # XGED2 — circuit multi-signataires.
            'routage', 'relance_cadence_jours', 'annule_le', 'annule_par',
            'signataires',
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
            'created_by', 'created_at', 'updated_at',
        ]

    def get_signataires(self, obj):
        return SignataireDemandeSerializer(
            obj.signataires.all(), many=True).data


class ChampSignatureSerializer(serializers.ModelSerializer):
    """XGED3 — Champ positionné sur le PDF à signer (demande OU modèle,
    exactement l'un des deux). `company` posée CÔTÉ SERVEUR (jamais lue du
    corps). `valeur` reste modifiable par cette API de GESTION (édition d'un
    placement) — le remplissage PUBLIC passe par `services.
    enregistrer_valeurs_champs`, jamais par cette route authentifiée."""
    class Meta:
        model = ChampSignature
        fields = [
            'id', 'demande', 'modele', 'type_champ', 'page',
            'x', 'y', 'largeur', 'hauteur', 'role', 'requis', 'valeur',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        demande = attrs.get('demande', getattr(self.instance, 'demande', None))
        modele = attrs.get('modele', getattr(self.instance, 'modele', None))
        if bool(demande) == bool(modele):
            raise serializers.ValidationError(
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
        return attrs


class SignataireDemandeSerializer(serializers.ModelSerializer):
    """XGED2 — Destinataire (signataire/copie/approbateur) d'une demande de
    signature multi-parties. LECTURE SEULE via l'API — créé/muté uniquement
    par `services` (création groupée, signature/refus par jeton public,
    notifications/relances)."""
    class Meta:
        model = SignataireDemande
        fields = [
            'id', 'demande', 'nom', 'email', 'telephone', 'ordre', 'role',
            'statut', 'notifie_le', 'derniere_relance_le', 'nb_relances',
            'date_action', 'motif_refus', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ModeleDocumentSerializer(serializers.ModelSerializer):
    """GED27 + GED28 — Modèle de document (fusion/mailing). `company`/`created_by`
    posés CÔTÉ SERVEUR (jamais lus du corps). Le corps HTML porte des jetons
    ``{{ champ }}`` fusionnés au rendu (`services.rendre_modele`). GED28 :
    `cabinet_cible`/`dossier_cible` portent la RÈGLE de classement automatique du
    document généré (le dossier peut être templaté par le contexte de fusion)."""
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        model = ModeleDocument
        fields = [
            'id', 'nom', 'description', 'categorie', 'corps_html',
            'cabinet_cible', 'dossier_cible', 'actif',
            'created_by', 'created_by_nom', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class JournalAccesSerializer(serializers.ModelSerializer):
    """GED35 — Entrée d'audit d'accès (LECTURE SEULE).

    Le journal est append-only : il n'est JAMAIS créé/modifié via cette API
    (l'écriture passe par `services.journaliser_acces`, côté serveur, au moment
    d'une lecture). Tous les champs sont en lecture seule."""
    document_nom = serializers.CharField(
        source='document.nom', read_only=True, default=None)
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True, default=None)

    class Meta:
        model = JournalAcces
        fields = [
            'id', 'document', 'document_nom',
            'utilisateur', 'utilisateur_nom',
            'type_acces', 'adresse_ip', 'created_at',
        ]
        read_only_fields = fields


class QuotaStockageSerializer(serializers.ModelSerializer):
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

    def get_utilise_octets(self, obj):
        return services.usage_stockage_octets(obj.company)

    def get_depasse(self, obj):
        return services.quota_depasse(obj.company)


class DepotPublicSerializer(serializers.ModelSerializer):
    """XGED7 — Gestion (côté propriétaire) d'un lien de dépôt public.

    `company`/`created_by`/`token` posés côté serveur. `url_publique` expose le
    chemin de dépôt (le frontend préfixe l'origine)."""
    folder_nom = serializers.CharField(source='folder.nom', read_only=True)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
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


class ExigenceDossierSerializer(serializers.ModelSerializer):
    """XGED8 — Modèle de checklist de pièces requises."""
    class Meta:
        model = ExigenceDossier
        fields = [
            'id', 'cabinet', 'folder', 'libelle', 'description',
            'obligatoire', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class DemandeDocumentSerializer(serializers.ModelSerializer):
    """XGED8 — Demande d'une pièce nommée (interne ou contact externe)."""
    folder_nom = serializers.CharField(source='folder.nom', read_only=True)
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True, default=None)

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


class ValidationOcrDocumentSerializer(serializers.ModelSerializer):
    """XGED13 — File de validation d'extraction OCR (score de confiance)."""
    document_nom = serializers.CharField(source='document.nom', read_only=True)
    valide_par_nom = serializers.CharField(
        source='valide_par.username', read_only=True, default=None)

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


class AnnotationDocumentSerializer(serializers.ModelSerializer):
    """XGED16 — Annotation/tampon posé sur l'image d'une version (couche
    séparée — n'affecte jamais le fichier original)."""
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default=None)

    class Meta:
        model = AnnotationDocument
        fields = [
            'id', 'version', 'type_annotation', 'page', 'x', 'y', 'contenu',
            'auteur', 'auteur_nom', 'created_at',
        ]
        read_only_fields = ['auteur', 'created_at']


class RegleDossierSerializer(serializers.ModelSerializer):
    """XGED19 — Règle d'action automatique à l'upload dans un dossier.

    `condition_group` doit être un groupe `core.rules` valide — validé côté
    vue via `core.rules.validate_condition_group` avant persistance."""
    folder_nom = serializers.CharField(source='folder.nom', read_only=True)

    class Meta:
        model = RegleDossier
        fields = [
            'id', 'folder', 'folder_nom', 'nom', 'condition_group', 'actions',
            'actif', 'ordre', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class RegleApprobationGedSerializer(serializers.ModelSerializer):
    """XGED20 — Routage conditionnel des approbations par métadonnées."""
    class Meta:
        model = RegleApprobationGed
        fields = [
            'id', 'libelle', 'condition_group', 'approbateurs', 'priorite',
            'actif', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class PlanificationDocumentSerializer(serializers.ModelSerializer):
    """XGED15 — Activité planifiée sur un document (« relancer le J+7 »)."""
    document_nom = serializers.CharField(source='document.nom', read_only=True)
    assigne_a_nom = serializers.CharField(
        source='assigne_a.username', read_only=True, default=None)

    class Meta:
        model = PlanificationDocument
        fields = [
            'id', 'document', 'document_nom', 'libelle', 'echeance',
            'assigne_a', 'assigne_a_nom', 'faite', 'notifiee',
            'created_by', 'created_at',
        ]
        read_only_fields = ['notifiee', 'created_by', 'created_at']
