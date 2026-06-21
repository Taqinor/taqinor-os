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
"""
from django.conf import settings
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
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
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
