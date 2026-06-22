"""Module GED — gestion documentaire (DMS) multi-tenant.

Transforme les fichiers épars de `records.Attachment` en un référentiel gouverné :
une arborescence (Cabinet → Folder), des documents versionnés et stockés dans
MinIO via les conventions de `records.storage` (clé `file_key`), avec un
checksum pour la déduplication.

Tout est company-stampé côté serveur et filtré par société, comme le reste de
l'ERP. Le fichier binaire lui-même ne quitte jamais le stockage objet — seul le
`file_key` (et ses métadonnées) vit en base.

GED2 — Cabinet + Folder arborescent avec un CHEMIN MATÉRIALISÉ (`path`, ex.
"/1/4/9/") : chaque dossier porte le chemin de ses ancêtres, ce qui rend les
requêtes de sous-arbre (descendants) triviales sans récursion SQL.

GED3 — Document + DocumentVersion : un document vit dans un dossier et porte N
versions ordonnées (numéro, file_key MinIO, checksum, uploadé par, date).

GED6 — DocumentLien : liaison polymorphe entre un Document et N'IMPORTE quel
objet métier autorisé (lead, client, devis, bon de commande, facture, chantier,
ticket SAV, outillage). On RÉUTILISE le registre `records.ALLOWED_TARGETS` et le
mécanisme ContentType déjà en place pour Activity/Attachment/Comment/TaggedItem
— on n'invente pas un nouveau schéma de FK générique. Company posée côté serveur.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class Cabinet(models.Model):
    """Espace documentaire racine (« armoire ») d'une société.

    Une société peut avoir plusieurs cabinets (ex. « Administratif »,
    « Technique », « RH ») ; chacun est la racine d'une arborescence de
    dossiers. Company posée côté serveur — jamais lue du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_cabinets')
    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        unique_together = [('company', 'nom')]
        verbose_name = 'Cabinet'
        verbose_name_plural = 'Cabinets'
        indexes = [
            models.Index(fields=['company', 'nom']),
        ]

    def __str__(self):
        return self.nom


class Folder(models.Model):
    """Dossier arborescent (GED2) — CHEMIN MATÉRIALISÉ.

    Un dossier appartient à un cabinet et peut avoir un dossier parent
    (self-FK). Le champ `path` est un chemin matérialisé de la forme
    "/<id_ancetre1>/<id_ancetre2>/…/<id_self>/" (les pk des ancêtres + soi),
    recalculé à chaque save : il rend une requête de sous-arbre triviale
    (`Folder.objects.filter(path__startswith=parent.path)`), sans récursion.

    Company posée côté serveur ; toujours cohérente avec celle du cabinet.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_folders')
    cabinet = models.ForeignKey(
        Cabinet, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='children')
    nom = models.CharField(max_length=200)
    # Chemin matérialisé : "/1/4/9/" — les pk des ancêtres puis soi, encadrés
    # de '/'. Renseigné/recalculé dans save() ; jamais lu du corps de requête.
    path = models.CharField(max_length=1000, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Dossier'
        verbose_name_plural = 'Dossiers'
        indexes = [
            models.Index(fields=['company', 'cabinet']),
            models.Index(fields=['parent']),
            models.Index(fields=['path']),
        ]

    def __str__(self):
        return self.nom

    def compute_path(self):
        """Construit le chemin matérialisé "/…/<self.pk>/" à partir du parent.

        Le parent porte déjà son propre chemin (matérialisé), donc on se
        contente d'y ajouter notre pk — pas de remontée récursive en base.
        Suppose un `self.pk` déjà attribué (on save APRÈS le premier insert)."""
        base = self.parent.path if (self.parent and self.parent.path) else '/'
        if not base.endswith('/'):
            base += '/'
        return f'{base}{self.pk}/'

    def save(self, *args, **kwargs):
        """Persiste, puis garantit un `path` matérialisé cohérent.

        Au premier insert le pk n'existe pas encore : on enregistre d'abord,
        puis on calcule le chemin et on met à jour le seul champ `path` si
        nécessaire (idempotent — pas de boucle de save)."""
        super().save(*args, **kwargs)
        expected = self.compute_path()
        if self.path != expected:
            self.path = expected
            super().save(update_fields=['path'])

    def descendants(self):
        """QuerySet des dossiers strictement sous celui-ci (sous-arbre).

        Trivial grâce au chemin matérialisé : tout descendant a un `path` qui
        COMMENCE par le nôtre (et n'est pas nous-même)."""
        return Folder.objects.filter(
            company=self.company, path__startswith=self.path
        ).exclude(pk=self.pk)


class Coffre(models.Model):
    """GED8 — Coffre-fort par employé/client (ACL propriétaire + admin).

    Un coffre-fort est un espace documentaire confidentiel rattaché à UN
    propriétaire : soit un employé (`proprietaire`, un User de la société), soit
    un client (`client_id`, référence string-FK vers `crm.Client` — jamais un
    import direct du modèle). Les documents placés dans un coffre (via
    `Document.coffre`) ne sont visibles QUE de leur propriétaire et des
    administrateurs de la société : le filtrage ACL est appliqué côté serveur
    dans les `selectors`/viewsets (jamais lu du corps de requête).

    Company posée côté serveur. Le coffre porte exactement un type de
    propriétaire : un employé OU un client (jamais les deux, jamais aucun).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_coffres')
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    # Propriétaire employé (User de la société) — exclusif avec `client_id`.
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_coffres')
    # Propriétaire client — référence string-FK vers crm.Client (cross-app via
    # selectors, jamais un import du modèle). Exclusif avec `proprietaire`.
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_coffres')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_coffres_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Coffre-fort'
        verbose_name_plural = 'Coffres-forts'
        indexes = [
            models.Index(fields=['company', 'proprietaire']),
            models.Index(fields=['company', 'client']),
        ]

    def __str__(self):
        return self.nom

    def is_accessible_by(self, user):
        """ACL — True si `user` peut accéder à ce coffre (propriétaire OU admin).

        Un employé voit son propre coffre (`proprietaire`). Un coffre client
        n'a pas d'utilisateur propriétaire : seuls les admins de la société y
        accèdent. Les administrateurs voient tous les coffres de leur société.
        """
        if user is None or not user.is_authenticated:
            return False
        if user.company_id != self.company_id:
            return False
        if getattr(user, 'is_admin_role', False) or user.is_superuser:
            return True
        return self.proprietaire_id == user.id


class Document(models.Model):
    """Document logique vivant dans un dossier (GED3).

    Le document est le conteneur stable (nom, dossier, société) ; son contenu
    binaire vit dans une ou plusieurs `DocumentVersion`. La version courante
    est simplement la plus récente (numéro le plus élevé). Company posée côté
    serveur — toujours cohérente avec celle du dossier.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_documents')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, related_name='documents')
    # GED8 — un document peut vivre dans un coffre-fort (ACL propriétaire+admin).
    # Quand `coffre` est non nul, seuls le propriétaire du coffre et les admins
    # voient/manipulent ce document (filtrage en `selectors`/viewset).
    coffre = models.ForeignKey(
        'Coffre', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='documents')
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    # GED10 — métadonnées typées configurables (réutilise `customfields`).
    # Un admin définit des `CustomFieldDef` sur le module « document » ; les
    # valeurs vivent ici, indexées par `code` (approche additive JSONField —
    # ajouter/retirer une définition ne touche jamais le schéma). Validé contre
    # les définitions actives via `customfields.serializers.validate_custom_data`.
    custom_data = models.JSONField(null=True, blank=True, default=dict)
    # GED11 — recherche plein-texte Postgres. `search_vector` est un tsvector
    # maintenu côté serveur (via `services.update_search_vector`) à partir du
    # nom, de la description, des tags et — quand GED12 l'alimente — du texte
    # OCR. Un index GIN dessus rend la recherche `@@` rapide. Le `texte_ocr`
    # est le texte extrait (vide par défaut ; rempli par l'indexation GED12).
    texte_ocr = models.TextField(blank=True, default='')
    search_vector = SearchVectorField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_documents_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        indexes = [
            models.Index(fields=['company', 'folder']),
            # GED11 — index GIN sur le tsvector pour la recherche plein-texte.
            GinIndex(fields=['search_vector'], name='ged_doc_search_gin'),
        ]

    def __str__(self):
        return self.nom


class DocumentVersion(models.Model):
    """Version d'un document (GED3) — pointeur vers un objet MinIO.

    Chaque version porte une clé objet MinIO (`file_key`, conventions de
    `records.storage` — bucket erp-uploads, le fichier ne quitte jamais le
    stockage objet), un `checksum` (SHA-256) pour la déduplication, un numéro
    de version incrémental (1, 2, 3…), l'auteur et la date. Company posée côté
    serveur — toujours cohérente avec celle du document.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_document_versions')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='versions')
    # Numéro de version incrémental par document (1, 2, 3…) — posé côté serveur.
    version = models.PositiveIntegerField(default=1)
    # Clé objet MinIO (bucket erp-uploads) — conventions records.storage.
    file_key = models.CharField(max_length=500)
    filename = models.CharField(max_length=255, blank=True, default='')
    size = models.PositiveIntegerField(default=0)
    mime = models.CharField(max_length=120, blank=True, default='')
    # SHA-256 (hex) du contenu pour la déduplication : deux versions de même
    # checksum dans une société pointent vers un contenu identique.
    checksum = models.CharField(max_length=64, blank=True, default='', db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_versions_uploadees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version', '-id']
        unique_together = [('document', 'version')]
        verbose_name = 'Version de document'
        verbose_name_plural = 'Versions de document'
        indexes = [
            models.Index(fields=['company', 'checksum']),
            models.Index(fields=['document', 'version']),
        ]

    def __str__(self):
        return f'{self.document} v{self.version}'


class DocumentLien(models.Model):
    """GED6 — Liaison polymorphe entre un Document et un objet métier.

    Rattache un document GED à N'IMPORTE quel enregistrement métier autorisé
    (lead, client, devis, bon de commande, facture, chantier/installation,
    ticket SAV, outillage) via le MÊME mécanisme ContentType que
    `records.Activity`/`Attachment`/`Comment`/`TaggedItem` — on ne réinvente pas
    de schéma de FK générique. La cible est bornée par `records.ALLOWED_TARGETS`
    (validation côté serveur : on ne lie jamais un type arbitraire).

    Company posée côté serveur (cohérente avec celle du document) — jamais lue du
    corps de requête. Un même document ne se lie qu'UNE fois à un objet donné.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_document_liens')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='liens')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_liens_crees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        unique_together = [('document', 'content_type', 'object_id')]
        verbose_name = 'Lien de document'
        verbose_name_plural = 'Liens de document'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['company', 'document']),
        ]

    def __str__(self):
        return f'{self.document} ↔ {self.content_type.model}:{self.object_id}'


class DocumentTag(models.Model):
    """GED9 — Taxonomie de tags documentaires (vocabulaire HIÉRARCHIQUE).

    Contrairement au tag plat partagé de `records.Tag`, la GED gère une
    TAXONOMIE : des tags peuvent porter un parent (`parent`, self-FK) pour
    former une arborescence de catégories (ex. « Juridique » → « Contrats » →
    « NDA »). Le `slug` est l'identifiant stable par société ; `couleur` un chip
    UI optionnel. Company posée côté serveur. Un tag est unique par (société,
    slug). On applique un tag à un document via `DocumentTagAssignment`.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_tags')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='enfants')
    nom = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110)
    couleur = models.CharField(max_length=7, blank=True, default='')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'id']
        unique_together = [('company', 'slug')]
        verbose_name = 'Tag documentaire'
        verbose_name_plural = 'Tags documentaires'
        indexes = [
            models.Index(fields=['company', 'slug']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return self.nom

    def ancetres(self):
        """Liste des tags ancêtres (du plus proche à la racine).

        Remonte la self-FK `parent` en restant borné à la société. Sert au
        chemin lisible « Juridique / Contrats / NDA » et à la garde anti-cycle.
        """
        chaine = []
        courant = self.parent
        seen = set()
        while courant is not None and courant.pk not in seen:
            seen.add(courant.pk)
            chaine.append(courant)
            courant = courant.parent
        return chaine


class DocumentTagAssignment(models.Model):
    """GED9 — Application d'un tag de la taxonomie à un document.

    Lien M2M explicite (through) entre `Document` et `DocumentTag` : un document
    porte N tags, un tag étiquette N documents. Unique par (document, tag).
    Company posée côté serveur (cohérente avec le document et le tag).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ged_tag_assignments')
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='tag_assignments')
    tag = models.ForeignKey(
        DocumentTag, on_delete=models.CASCADE, related_name='assignments')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ged_tag_assignments_crees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        unique_together = [('document', 'tag')]
        verbose_name = 'Affectation de tag'
        verbose_name_plural = 'Affectations de tag'
        indexes = [
            models.Index(fields=['company', 'document']),
            models.Index(fields=['tag']),
        ]

    def __str__(self):
        return f'{self.document} #{self.tag}'
