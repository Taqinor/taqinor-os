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
        related_name='kb_articles',
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
        related_name='kb_articles',
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
