"""Modèles du groupe NTMIG — projets de migration ERP sortants.

Trois modèles :

* :class:`ProjetMigration` — le conteneur d'une migration (une source, N lots
  d'entités).
* :class:`LotMigration` — un lot par entité (clients, produits, devis…) ; le
  chargement effectif est DÉLÉGUÉ à ``apps.dataimport`` (traçabilité par FK
  CHAÎNE ``import_job`` vers ``dataimport.ImportJob``, jamais un import
  parallèle ni un second journal).
* :class:`RapportReconciliation` — LE différenciateur : comptages et totaux
  financiers source vs cible ; un lot ne passe jamais « réconcilié » sans un
  rapport ``conforme=True`` ou une dérogation motivée (NTMIG5).

Multi-société : tout hérite de ``core.models.TenantModel`` (FK ``company`` +
horodatage). Les FK vers d'autres apps sont des références par CHAÎNE
(``'dataimport.ImportJob'``), jamais un import direct de leurs modèles.
Aucune écriture SQL vers Odoo (règle #1).
"""
from decimal import Decimal

from django.db import models

from core.models import TenantModel


class ProjetMigration(TenantModel):
    """Conteneur d'une migration : une source, N lots d'entités."""

    class Source(models.TextChoices):
        ODOO = 'odoo', 'Odoo'
        SAGE = 'sage', 'Sage'
        EXCEL = 'excel', 'Excel'
        CSV_GENERIQUE = 'csv_generique', 'CSV générique'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ANALYSE = 'analyse', 'Analyse'
        CHARGEMENT = 'chargement', 'Chargement'
        RECONCILIATION = 'reconciliation', 'Réconciliation'
        TERMINE = 'termine', 'Terminé'
        ECHOUE = 'echoue', 'Échoué'

    nom = models.CharField(max_length=200)
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.EXCEL)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    cree_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='projets_migration_crees')
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut']),
        ]
        verbose_name = 'Projet de migration'
        verbose_name_plural = 'Projets de migration'

    def __str__(self):
        return f'{self.nom} ({self.get_source_display()})'


class LotMigration(TenantModel):
    """Un lot par entité dans un projet.

    Le chargement effectif est délégué au moteur ``dataimport`` ;
    ``import_job`` trace le commit réel (journal unique). Les compteurs miroir
    (source/créés/màj/erreurs) alimentent le rapport de réconciliation.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ANALYSE = 'analyse', 'Analysé'
        CHARGE = 'charge', 'Chargé'
        RECONCILIE = 'reconcilie', 'Réconcilié'
        ECHOUE = 'echoue', 'Échoué'

    projet = models.ForeignKey(
        ProjetMigration,
        # on_delete: composition — un lot n'existe que rattaché à son projet.
        on_delete=models.CASCADE,
        related_name='lots')
    entite = models.CharField(
        max_length=50,
        help_text="Clé de cible d'import ``dataimport.TARGETS`` (clients, "
                  "products, fournisseurs…).")
    ordre = models.PositiveIntegerField(default=0)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    # FK-CHAÎNE vers dataimport (jamais un import direct de son modèle).
    import_job = models.ForeignKey(
        'dataimport.ImportJob', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_migration')

    # Compteurs miroir du dernier chargement (base du reconcile).
    source_lignes = models.PositiveIntegerField(default=0)
    crees = models.PositiveIntegerField(default=0)
    maj = models.PositiveIntegerField(default=0)
    erreurs = models.PositiveIntegerField(default=0)
    # Somme des colonnes montant déclarées par le kit (reconcile financier).
    source_montant = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)

    # NTMIG5 — dérogation explicite « pas de succès sans reconcile ».
    derogation_reconcile = models.BooleanField(default=False)
    derogation_motif = models.TextField(blank=True, default='')
    derogation_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_migration_deroges')
    derogation_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['projet', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'projet']),
        ]
        verbose_name = 'Lot de migration'
        verbose_name_plural = 'Lots de migration'

    def __str__(self):
        return f'{self.projet_id}:{self.entite} ({self.statut})'


class RapportReconciliation(TenantModel):
    """Rapport de réconciliation d'un lot.

    Compare les comptages/totaux SOURCE (posés à l'analyse) aux comptages
    CIBLE réels après chargement. ``conforme`` n'est vrai que si les comptages
    ET les totaux financiers matchent à la tolérance près.

    Un rapport est un CONSTAT HORODATÉ : on en crée un nouveau à chaque
    réconciliation, on n'écrase jamais le précédent (l'historique des écarts
    est la pièce justificative remise au client migré).
    """

    lot = models.ForeignKey(
        LotMigration,
        # on_delete: composition — un rapport n'existe que pour son lot.
        on_delete=models.CASCADE,
        related_name='rapports')

    nb_source = models.PositiveIntegerField(default=0)
    nb_cible_crees = models.PositiveIntegerField(default=0)
    nb_cible_existants = models.PositiveIntegerField(default=0)
    nb_erreurs = models.PositiveIntegerField(default=0)

    total_financier_source = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)
    total_financier_cible = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)
    ecart_financier = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True)

    ecarts = models.JSONField(default=list, blank=True)
    conforme = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'lot']),
        ]
        verbose_name = 'Rapport de réconciliation'
        verbose_name_plural = 'Rapports de réconciliation'

    def save(self, *args, **kwargs):
        src = self.total_financier_source
        cib = self.total_financier_cible
        if src is not None and cib is not None:
            self.ecart_financier = Decimal(cib) - Decimal(src)
            # Un ``update_fields`` restreint ne doit pas faire disparaître
            # silencieusement l'écart qu'on vient de recalculer.
            champs = kwargs.get('update_fields')
            if champs is not None and 'ecart_financier' not in champs:
                kwargs['update_fields'] = list(champs) + ['ecart_financier']
        super().save(*args, **kwargs)

    def __str__(self):
        etat = 'conforme' if self.conforme else 'écarts'
        return f'Reconcile lot {self.lot_id} ({etat})'
