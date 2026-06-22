"""Modèles de la Base de connaissances interne (module `apps.kb`).

Référentiel d'articles internes (procédures, fiches techniques, FAQ) destinés
aux équipes. Multi-société : chaque modèle porte un FK ``company`` posé côté
serveur (jamais lu du corps de requête). Entièrement additif.
"""
from django.conf import settings
from django.db import models


class KbArticle(models.Model):
    """Article de la base de connaissances interne d'une société."""
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PUBLIE = 'publie', 'Publié'
        OBSOLETE = 'obsolete', 'Obsolète'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_articles',
        verbose_name='Société',
    )
    titre = models.CharField(max_length=255, verbose_name='Titre')
    corps = models.TextField(blank=True, default='', verbose_name='Contenu')
    categorie = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Catégorie')
    tags = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Tags')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kb_app_articles',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'
        ordering = ['-id']

    def __str__(self):
        return self.titre


class KbArticleVersion(models.Model):
    """Instantané versionné du contenu d'un :class:`KbArticle`.

    À chaque mise à jour de l'article (ou via l'action explicite ``publier`` /
    ``nouvelle-version``) on fige titre + contenu dans une nouvelle ligne. Le
    numéro (``version``) est incrémental PAR article, calculé côté serveur
    (max(version)+1 — JAMAIS count()+1, sujet aux collisions). La société est
    posée côté serveur et toujours cohérente avec celle de l'article.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_article_versions',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='Article',
    )
    version = models.PositiveIntegerField(
        default=1, verbose_name='Numéro de version')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    contenu = models.TextField(blank=True, default='', verbose_name='Contenu')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kb_app_article_versions',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Version d’article'
        verbose_name_plural = 'Versions d’article'
        ordering = ['-version', '-id']
        unique_together = [('article', 'version')]
        indexes = [
            models.Index(fields=['company', 'article']),
            models.Index(fields=['article', 'version']),
        ]

    def __str__(self):
        return f'{self.titre} v{self.version}'


class KbArticleLien(models.Model):
    """Lien LÂCHE d'un article vers un objet métier d'une AUTRE app.

    Permet de rattacher un article de la base de connaissances à un produit
    (``stock``), un équipement (``sav``) ou un type d'intervention SANS aucun
    FK dur : la cible est désignée par un couple typé ``(type_cible, cible_id)``
    — jamais un import du modèle d'une autre app. Les écrans SAV / chantier
    peuvent ainsi remonter les articles contextuels (« quels articles sont liés
    au produit X »). Le ``libelle`` met en cache un libellé d'affichage ; les
    sélecteurs (``selectors.py``) l'enrichissent au vol quand l'app cible expose
    un sélecteur de lecture, et dégradent proprement (libellé stocké seul) sinon.
    """
    class TypeCible(models.TextChoices):
        PRODUIT = 'produit', 'Produit'
        EQUIPEMENT = 'equipement', 'Équipement'
        TYPE_INTERVENTION = 'type_intervention', "Type d'intervention"

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='kb_app_article_liens',
        verbose_name='Société',
    )
    article = models.ForeignKey(
        KbArticle,
        on_delete=models.CASCADE,
        related_name='liens',
        verbose_name='Article',
    )
    type_cible = models.CharField(
        max_length=20, choices=TypeCible.choices, verbose_name='Type de cible')
    # PK de l'objet cible dans son app (référence lâche, aucun FK dur).
    cible_id = models.PositiveIntegerField(verbose_name='ID de la cible')
    # Libellé d'affichage mis en cache (fallback quand l'app cible n'a pas de
    # sélecteur d'enrichissement).
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Lien de l'article"
        verbose_name_plural = "Liens de l'article"
        ordering = ['id']
        unique_together = [('article', 'type_cible', 'cible_id')]
        indexes = [
            models.Index(fields=['company', 'type_cible', 'cible_id']),
        ]

    def __str__(self):
        return f'{self.article_id} → {self.type_cible} #{self.cible_id}'
