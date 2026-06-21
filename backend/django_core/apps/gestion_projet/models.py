"""Modèles de la Gestion de projet (module `apps.gestion_projet`).

Socle multi-chantier : un ``Projet`` regroupe un ou plusieurs chantiers
(``ProjetChantier``) et porte le suivi de réalisation (statut, dates, budget
INTERNE). Les références transverses (client CRM, chantier installations) sont
des liens LÂCHES par identifiant — jamais d'import des modèles d'une autre app.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Aucun comportement existant n'est modifié — ce
module est entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Projet(models.Model):
    """Un projet multi-chantier d'une société (suivi de réalisation).

    Le ``client_id`` référence LÂCHEMENT un ``crm.Client`` (aucun FK dur) ; le
    ``budget_total`` est une donnée INTERNE de pilotage, jamais exposée au
    client final.
    """
    class Statut(models.TextChoices):
        PROSPECT = 'prospect', 'Prospect'
        EN_COURS = 'en_cours', 'En cours'
        SUSPENDU = 'suspendu', 'Suspendu'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projets',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.EN_COURS, verbose_name='Statut')
    # Référence lâche vers crm.Client (aucun FK dur).
    client_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du client')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de fin prévue')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projets_responsable',
        verbose_name='Responsable',
    )
    # Budget INTERNE de pilotage — jamais exposé au client final.
    budget_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Budget total')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Projet'
        verbose_name_plural = 'Projets'
        unique_together = [('company', 'code')]
        ordering = ['-id']

    def __str__(self):
        return f'{self.code} — {self.nom}'


class ProjetChantier(models.Model):
    """Rattachement LÂCHE d'un chantier (installations.Chantier) à un projet.

    Le ``chantier_id`` référence LÂCHEMENT un ``installations.Chantier`` (aucun
    FK dur) ; un même projet peut agréger plusieurs chantiers.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_chantiers',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='chantiers',
        verbose_name='Projet',
    )
    # Référence lâche vers installations.Chantier (aucun FK dur).
    chantier_id = models.PositiveIntegerField(verbose_name='ID du chantier')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Chantier du projet'
        verbose_name_plural = 'Chantiers du projet'
        ordering = ['id']

    def __str__(self):
        return f'{self.projet.code} ← chantier {self.chantier_id}'
