from rest_framework import serializers

from .models import (
    Cabinet, Coffre, Document, DocumentLien, DocumentVersion, Folder,
)
from . import services


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

    class Meta:
        model = DocumentVersion
        # version / company posés côté serveur (services.add_version).
        fields = [
            'id', 'document', 'version', 'file_key', 'filename', 'size',
            'mime', 'checksum', 'uploaded_by', 'uploaded_by_nom', 'created_at',
        ]
        read_only_fields = ['version', 'uploaded_by', 'created_at']
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

    class Meta:
        model = Document
        # `company` + `created_by` posés côté serveur.
        fields = [
            'id', 'folder', 'folder_nom', 'coffre', 'nom', 'description',
            'created_by', 'created_by_nom', 'version_count', 'derniere_version',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_version_count(self, obj):
        return obj.versions.count()

    def get_derniere_version(self, obj):
        last = obj.versions.order_by('-version').first()
        return last.version if last else None

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
