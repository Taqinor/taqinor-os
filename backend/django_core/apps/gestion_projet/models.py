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

    Le cycle de vie ``statut`` est une machine à états PROPRE au projet
    d'installation solaire — totalement DISTINCTE des étapes du tunnel CRM de
    ``STAGES.py`` (règle #2) : il ne réutilise NI n'importe AUCUNE clé/étiquette
    de ``STAGES.py``. Le ``statut`` n'est jamais posé depuis le corps de
    requête : seules les actions de transition (voir ``views.py``) le déplacent.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        EN_PAUSE = 'en_pause', 'En pause'
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
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
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


class ProjetLien(models.Model):
    """Lien LÂCHE d'un projet vers un document métier d'une AUTRE app.

    Permet de rattacher un projet à un devis (``ventes``), une facture
    (``ventes``), un ticket SAV (``sav``) ou un achat (``stock``) SANS aucun FK
    dur : la cible est désignée par un couple typé ``(type_cible, cible_id)`` —
    jamais un import du modèle d'une autre app. Le ``libelle`` met en cache un
    libellé d'affichage ; les sélecteurs (``selectors.py``) l'enrichissent au
    vol quand l'app cible expose un sélecteur de lecture, et dégradent
    proprement (libellé stocké seul) sinon.
    """
    class TypeCible(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        FACTURE = 'facture', 'Facture'
        TICKET = 'ticket', 'Ticket SAV'
        ACHAT = 'achat', 'Achat'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_liens',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='liens',
        verbose_name='Projet',
    )
    type_cible = models.CharField(
        max_length=10, choices=TypeCible.choices, verbose_name='Type de cible')
    # PK de l'objet cible dans son app (référence lâche, aucun FK dur).
    cible_id = models.PositiveIntegerField(verbose_name='ID de la cible')
    # Libellé d'affichage mis en cache (fallback quand l'app cible n'a pas de
    # sélecteur d'enrichissement).
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Lien du projet'
        verbose_name_plural = 'Liens du projet'
        ordering = ['id']
        unique_together = [('projet', 'type_cible', 'cible_id')]

    def __str__(self):
        return f'{self.projet.code} → {self.type_cible} #{self.cible_id}'


class ProjetActivity(models.Model):
    """Journal minimal des transitions de statut d'un ``Projet``.

    Chaque changement de statut appliqué par une action de transition
    (``views.py``) y est tracé côté serveur : ancien → nouveau statut, auteur,
    horodatage. La société et l'auteur sont TOUJOURS posés côté serveur, jamais
    lus du corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_activites',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='activites',
        verbose_name='Projet',
    )
    old_value = models.CharField(
        max_length=15, blank=True, default='', verbose_name='Ancien statut')
    new_value = models.CharField(
        max_length=15, blank=True, default='', verbose_name='Nouveau statut')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projet_activites',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Activité projet'
        verbose_name_plural = 'Activités projet'
        ordering = ['-date_creation', '-id']
        indexes = [models.Index(
            fields=['projet', '-date_creation'],
            name='gp_proj_activity_idx')]

    def __str__(self):
        return f'{self.projet_id} {self.old_value}→{self.new_value}'.strip()
