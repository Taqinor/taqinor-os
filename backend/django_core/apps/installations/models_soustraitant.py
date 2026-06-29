"""
FG304 — Référentiel des sous-traitants chantier.

``SousTraitant`` est l'annuaire des prestataires de MAIN-D'ŒUVRE sous-traitée du
chantier (terrassement, génie civil, électricité, levage, transport…) : qui ils
sont (raison sociale, métier), comment les joindre (contact, téléphone, e-mail,
adresse) et leurs identifiants administratifs marocains (ICE, RIB).

Il est DISTINCT du fournisseur de MATÉRIEL : un fournisseur vend des panneaux,
onduleurs, câbles ; un sous-traitant vend une prestation de pose/travaux. Les
deux annuaires ne se mélangent jamais — ce modèle vit dans l'app installations
(réalisation chantier), à côté du budget de sous-traitance (``BudgetProjet.
budget_sous_traitance``) qu'il viendra plus tard documenter.

Couche INDÉPENDANTE des trois couches de statuts de l'OS (entonnoir STAGES.py,
statut document ventes, statut chantier) : un sous-traitant n'a AUCUN statut
métier — seulement un drapeau ``actif`` d'archivage. Son enum de métier est
PROPRE à l'app installations (jamais STAGES.py).

Additif & multi-tenant : on AJOUTE une table avec une FK ``company`` posée côté
serveur, jamais lue du corps de la requête.
"""
from django.conf import settings
from django.db import models


class SousTraitant(models.Model):
    """FG304 — un sous-traitant chantier (prestataire de main-d'œuvre), DISTINCT
    d'un fournisseur de matériel.

    Multi-tenant : la société est posée côté serveur. ``metier`` ventile le corps
    de métier (terrassement / génie civil / électricité / levage / transport /
    autre) ; ``ice`` et ``rib`` portent les identifiants administratifs marocains.
    ``actif`` permet d'archiver un sous-traitant sans le supprimer."""

    class Metier(models.TextChoices):
        TERRASSEMENT = 'terrassement', 'Terrassement'
        GENIE_CIVIL = 'genie_civil', 'Génie civil'
        ELECTRICITE = 'electricite', 'Électricité'
        LEVAGE = 'levage', 'Levage'
        TRANSPORT = 'transport', 'Transport'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_sous_traitants')
    raison_sociale = models.CharField(max_length=255)
    # max_length=20 couvre le plus long code de Metier ('terrassement' = 12).
    metier = models.CharField(
        max_length=20, choices=Metier.choices, default=Metier.AUTRE)
    contact_nom = models.CharField(max_length=255, blank=True, null=True)
    telephone = models.CharField(max_length=40, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    # ICE marocain = 15 chiffres ; RIB marocain = 24 chiffres. On laisse de la
    # marge (CharField, jamais numérique : les zéros de tête comptent).
    ice = models.CharField(max_length=32, blank=True, null=True)
    rib = models.CharField(max_length=34, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    actif = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_sous_traitants_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sous-traitant'
        verbose_name_plural = 'Sous-traitants'
        ordering = ['raison_sociale']
        indexes = [
            # Noms d'index ≤ 30 caractères (contrainte Django/Postgres).
            models.Index(fields=['company', 'metier'],
                         name='idx_soustrait_co_metier'),
            models.Index(fields=['company', 'actif'],
                         name='idx_soustrait_co_actif'),
        ]

    def __str__(self):
        return f'{self.raison_sociale} · {self.get_metier_display()}'
