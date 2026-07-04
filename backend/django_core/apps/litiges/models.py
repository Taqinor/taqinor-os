"""Modèles des Réclamations & litiges (module `apps.litiges`).

Registre des réclamations clients et litiges (financier, qualité, délai…),
rattachables à un document source (facture/lead/chantier/ticket) par une
référence souple (type + id) — jamais un import cross-app de modèle.
Multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Reclamation(models.Model):
    """Réclamation ou litige d'une société."""
    class TypeReclamation(models.TextChoices):
        FINANCIER = 'financier', 'Financier'
        QUALITE = 'qualite', 'Qualité'
        DELAI = 'delai', 'Délai'
        COMMERCIAL = 'commercial', 'Commercial'
        # XFAC21 — dossier contentieux / passage en recouvrement externe
        # (avocat / société de recouvrement), distinct d'un simple litige
        # financier en cours de discussion amiable.
        RECOUVREMENT = 'recouvrement', 'Recouvrement'
        AUTRE = 'autre', 'Autre'

    class Gravite(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYENNE = 'moyenne', 'Moyenne'
        ELEVEE = 'elevee', 'Élevée'

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        EN_TRAITEMENT = 'en_traitement', 'En traitement'
        RESOLUE = 'resolue', 'Résolue'
        REJETEE = 'rejetee', 'Rejetée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='litiges_reclamations',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    type_reclamation = models.CharField(
        max_length=20, choices=TypeReclamation.choices,
        default=TypeReclamation.AUTRE, verbose_name='Type de réclamation')
    gravite = models.CharField(
        max_length=10, choices=Gravite.choices,
        default=Gravite.MOYENNE, verbose_name='Gravité')
    objet = models.CharField(max_length=255, verbose_name='Objet')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Origine documentaire (facture/lead/chantier/ticket) — string FK souple
    # pour ne jamais importer les modèles d'une autre app.
    source_type = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Type de document source')
    source_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du document source')
    montant_conteste = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant contesté')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.OUVERTE, verbose_name='Statut')
    # LITIGE3 — quand True (par défaut), ce litige suspend les relances
    # automatiques sur la facture liée (source_type='facture', source_id=…).
    # Passe à False si le gestionnaire décide de laisser les relances continuer
    # malgré le litige ouvert.
    bloque_relances = models.BooleanField(
        default=True,
        verbose_name='Bloque les relances',
        help_text="Si coché, suspend les relances automatiques sur la facture "
                  "liée tant que ce litige est ouvert.")
    # LITIGE4 — Litige qualité ↔ QHSE. Liens lâches par id (jamais un import
    # cross-app des modèles QHSE) vers la non-conformité (NCR) et l'audit fin de
    # chantier rattachés à ce litige qualité. La lecture des données QHSE passe
    # par ``apps.qhse.selectors`` (import fonction-local). Null = non rattaché.
    ncr_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID de la non-conformité QHSE (NCR)')
    audit_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="ID de l'audit fin de chantier QHSE")
    # LITIGE5 — Capture du concurrent/motif sur deal perdu (étend FG242).
    # Quand un deal perdu escalade en litige (typiquement commercial), on saisit
    # ICI, au niveau du litige, le concurrent gagnant + son prix + le motif de la
    # perte. Le lead perdu d'origine est référencé par le couple lâche déjà
    # présent (``source_type='lead'`` / ``source_id``) — référence string-FK,
    # jamais un import des modèles ``apps.crm``. Tous les champs sont optionnels
    # (l'information n'est pas toujours connue) et entièrement additifs.
    concurrent_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Concurrent gagnant',
        help_text="Nom du concurrent qui a remporté l'affaire. Vide si inconnu.")
    concurrent_prix = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        verbose_name='Prix du concurrent',
        help_text='Prix proposé par le concurrent. Vide si inconnu.')
    concurrent_devise = models.CharField(
        max_length=8, blank=True, default='MAD',
        verbose_name='Devise du prix concurrent')
    motif_perte = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Motif de la perte',
        help_text='Raison pour laquelle le deal a été perdu (texte libre).')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reclamations_creees',
        verbose_name='Créée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Réclamation'
        verbose_name_plural = 'Réclamations'
        ordering = ['-id']

    def __str__(self):
        return self.objet


class ReclamationActivity(models.Model):
    """Historique « chatter » d'une réclamation (style Odoo), modèle maison.

    Deux familles d'entrées :
      - automatiques : changements de statut suivis (ancien → nouveau statut,
        utilisateur, horodatage) — écrites côté serveur au niveau de l'API,
        jamais par le navigateur ;
      - manuelles : notes libres (commentaire, suivi…).
    La société et l'auteur sont toujours posés côté serveur.
    """

    class Kind(models.TextChoices):
        LOG = 'log', 'Changement de statut'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='litiges_activites',
        verbose_name='Société',
    )
    reclamation = models.ForeignKey(
        Reclamation,
        on_delete=models.CASCADE,
        related_name='activites',
        verbose_name='Réclamation',
    )
    type = models.CharField(
        max_length=10, choices=Kind.choices, verbose_name='Type')
    old_value = models.CharField(
        max_length=15, blank=True, default='', verbose_name='Ancien statut')
    new_value = models.CharField(
        max_length=15, blank=True, default='', verbose_name='Nouveau statut')
    message = models.TextField(
        blank=True, default='', verbose_name='Message')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='litiges_activites',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Activité réclamation'
        verbose_name_plural = 'Activités réclamation'
        ordering = ['-date_creation', '-id']
        indexes = [models.Index(
            fields=['reclamation', '-date_creation'],
            name='litiges_rec_reclama_idx')]

    def __str__(self):
        return f"{self.reclamation_id} {self.type}".strip()
