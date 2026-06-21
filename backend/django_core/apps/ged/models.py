"""Modèles de la Gestion documentaire (GED) — module `apps.ged`.

Socle d'une gestion électronique des documents multi-société :

* ``Dossier`` (GED2) — arborescence de dossiers à CHEMIN MATÉRIALISÉ (`chemin`,
  ex. "/1/4/9/") : chaque dossier porte le chemin de ses ancêtres, ce qui rend
  les requêtes de sous-arbre triviales sans récursion SQL.
* ``Document`` (GED3) — document logique vivant dans un dossier, avec un statut
  (brouillon/publié/archivé) et un auteur.
* ``DocumentVersion`` (GED3) — version numérotée d'un document, pointeur vers un
  objet MinIO (`file_key`) avec un checksum pour la déduplication.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Entièrement additif.
"""
from django.conf import settings
from django.db import models


class Dossier(models.Model):
    """Dossier arborescent (GED2) — CHEMIN MATÉRIALISÉ.

    Un dossier peut avoir un dossier parent (self-FK). Le champ ``chemin`` est un
    chemin matérialisé porté par le serveur, qui rend une requête de sous-arbre
    triviale (``Dossier.objects.filter(chemin__startswith=parent.chemin)``) sans
    récursion. Company posée côté serveur — jamais lue du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ged_dossiers',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='enfants',
        verbose_name='Dossier parent',
    )
    # Chemin matérialisé (ex. "/1/4/9/") — posé côté serveur, jamais du corps.
    chemin = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Chemin')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Dossier'
        verbose_name_plural = 'Dossiers'
        ordering = ['chemin', 'nom']

    def __str__(self):
        return self.nom


class Document(models.Model):
    """Document logique vivant dans un dossier (GED3).

    Le document est le conteneur stable (titre, dossier, statut, société) ; son
    contenu binaire vit dans une ou plusieurs ``DocumentVersion``. Company posée
    côté serveur — jamais lue du corps de requête.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PUBLIE = 'publie', 'Publié'
        ARCHIVE = 'archive', 'Archivé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ged_documents',
        verbose_name='Société',
    )
    dossier = models.ForeignKey(
        Dossier,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='documents',
        verbose_name='Dossier',
    )
    titre = models.CharField(max_length=255, verbose_name='Titre')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ged_documents_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-id']

    def __str__(self):
        return self.titre


class DocumentVersion(models.Model):
    """Version d'un document (GED3) — pointeur vers un objet MinIO.

    Chaque version porte une clé objet MinIO (``file_key``, le fichier ne quitte
    jamais le stockage objet), un ``checksum`` pour la déduplication et un numéro
    de version incrémental. Company posée côté serveur — toujours cohérente avec
    celle du document.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ged_versions',
        verbose_name='Société',
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='Document',
    )
    numero_version = models.PositiveIntegerField(
        default=1, verbose_name='Numéro de version')
    # Clé objet MinIO — le contenu binaire ne vit jamais en base.
    file_key = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Clé objet MinIO')
    filename = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Nom de fichier')
    mime = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Type MIME')
    taille = models.PositiveIntegerField(default=0, verbose_name='Taille')
    checksum = models.CharField(
        max_length=64, blank=True, default='', verbose_name='Checksum')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Version de document'
        verbose_name_plural = 'Versions de document'
        ordering = ['-numero_version']
        unique_together = [('document', 'numero_version')]

    def __str__(self):
        return f'{self.document} v{self.numero_version}'
