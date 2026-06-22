from rest_framework import serializers

from .models import Cabinet, Document, DocumentLien, DocumentVersion, Folder


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
            'id', 'folder', 'folder_nom', 'nom', 'description',
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
