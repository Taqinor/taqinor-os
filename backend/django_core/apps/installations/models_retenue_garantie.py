"""
FG309 — Retenue de garantie sur sous-traitant (pratique BTP marocaine).

``RetenueGarantieSousTraitant`` matérialise le pourcentage du montant d'un ordre
de travaux (``OrdreSousTraitance``, FG305) RETENU au sous-traitant jusqu'à la
levée des réserves (réception définitive). C'est une pratique standard du BTP au
Maroc : on bloque typiquement 5 à 10 % du montant, libéré à la levée.

La retenue ne modifie AUCUN montant existant : elle se calcule sur le montant
(réalisé sinon engagé) de l'ordre et n'est « libérée » qu'en posant ``levee`` +
``date_levee``. Montants INTERNES — jamais client-facing. Couche INDÉPENDANTE des
statuts de l'OS.

Additif & multi-tenant : on AJOUTE une table avec une FK ``company`` posée côté
serveur, jamais lue du corps de la requête.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class RetenueGarantieSousTraitant(models.Model):
    """FG309 — retenue de garantie (%) sur un ordre de sous-traitance, bloquée
    jusqu'à la levée des réserves.

    Multi-tenant : la société est posée côté serveur. ``montant_retenu`` est
    dérivé du montant de l'ordre × pourcentage. Montants INTERNES."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_retenues_garantie')
    # Une retenue porte sur UN ordre de travaux. CASCADE : la retenue n'a pas de
    # sens sans son ordre.
    ordre = models.ForeignKey(
        'installations.OrdreSousTraitance', on_delete=models.CASCADE,
        related_name='retenues_garantie')
    # Pourcentage retenu (0–100). DecimalField : on retient parfois 7,5 %.
    pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10'),
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('100'))])
    # Réserves levées ? La retenue n'est libérée qu'une fois ce drapeau posé.
    levee = models.BooleanField(default=False)
    date_constitution = models.DateField(null=True, blank=True)
    date_levee = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_retenues_garantie_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Retenue de garantie sous-traitant'
        verbose_name_plural = 'Retenues de garantie sous-traitant'
        ordering = ['-date_creation']
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'levee'],
                         name='idx_rg_co_levee'),
            models.Index(fields=['company', 'ordre'],
                         name='idx_rg_co_ordre'),
        ]

    def __str__(self):
        return f'{self.pourcentage}% · ordre {self.ordre_id}'

    @property
    def montant_base(self):
        """Montant de référence : réalisé de l'ordre s'il existe, sinon engagé.
        INTERNE."""
        ordre = self.ordre
        if ordre is None:
            return Decimal('0')
        base = ordre.montant_realise
        if base is None:
            base = ordre.montant or Decimal('0')
        return base

    @property
    def montant_retenu(self):
        """Montant bloqué = base × pourcentage / 100 (INTERNE)."""
        pct = self.pourcentage or Decimal('0')
        return (self.montant_base * pct / Decimal('100')).quantize(
            Decimal('0.01'))

    @property
    def montant_a_liberer(self):
        """Montant restant bloqué tant que les réserves ne sont pas levées
        (0 une fois levée). INTERNE."""
        if self.levee:
            return Decimal('0')
        return self.montant_retenu
