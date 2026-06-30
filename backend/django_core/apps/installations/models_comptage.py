"""
FG324 — Sessions de comptage tournant (cycle count ABC).

FG63 (`stock.InventaireSession`) fait un comptage PHYSIQUE one-shot de tout le
stock. FG324 ajoute le comptage TOURNANT : des sessions partielles RÉCURRENTES
ciblées par zone (`stock.EmplacementStock`) et par classe ABC (les SKU à forte
valeur, classe A, sont comptés plus souvent). Chaque ligne compare la quantité
théorique (snapshot serveur) à la quantité comptée et calcule l'écart.

Cross-app : `stock.Produit` / `stock.EmplacementStock` en STRING-FK ; la quantité
théorique est lue via `stock.selectors` (jamais d'import du modèle stock). Couche
de CONSTAT : elle n'ajuste pas le stock canonique (l'ajustement reste piloté par
le module stock). Additif & multi-tenant : FK `company` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class SessionComptage(models.Model):
    """FG324 — session de comptage tournant ciblée (zone + classe ABC).

    Référence ``CYC-YYYYMM-NNNN`` anti-collision. Statut : planifié → en cours →
    terminé. ``classe_abc`` filtre les SKU à compter ; ``emplacement`` cible une
    zone."""

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'

    class ClasseABC(models.TextChoices):
        A = 'A', 'A (forte valeur)'
        B = 'B', 'B (valeur moyenne)'
        C = 'C', 'C (faible valeur)'
        TOUTES = 'toutes', 'Toutes'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_sessions_comptage')
    reference = models.CharField(max_length=50)
    intitule = models.CharField(max_length=255, blank=True, null=True)
    emplacement = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_sessions_comptage')
    classe_abc = models.CharField(
        max_length=10, choices=ClasseABC.choices, default=ClasseABC.TOUTES)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PLANIFIE)
    date_planifiee = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_sessions_comptage_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Session de comptage tournant'
        verbose_name_plural = 'Sessions de comptage tournant'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_cyc_co_statut'),
            models.Index(fields=['company', 'classe_abc'],
                         name='idx_cyc_co_classe'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'


class ComptageLigne(models.Model):
    """FG324 — ligne de comptage : SKU + quantité théorique (snapshot) +
    quantité comptée. L'écart est dérivé (comptée − théorique)."""

    session = models.ForeignKey(
        SessionComptage, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_comptage_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite_theorique = models.IntegerField(default=0)
    quantite_comptee = models.IntegerField(null=True, blank=True)
    compte = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Ligne de comptage'
        verbose_name_plural = 'Lignes de comptage'
        ordering = ['session_id', 'id']
        indexes = [
            models.Index(fields=['session'], name='idx_cycl_session'),
            models.Index(fields=['produit'], name='idx_cycl_produit'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id}'

    @property
    def ecart(self):
        """Écart constaté (comptée − théorique), ou None si pas encore compté."""
        if self.quantite_comptee is None:
            return None
        return self.quantite_comptee - self.quantite_theorique
