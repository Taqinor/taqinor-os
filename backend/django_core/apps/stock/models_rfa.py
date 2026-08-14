"""NTDST5 — Remises arrière / RFA fournisseurs.

Un accord de RFA dit : « si j'achète plus de X MAD chez toi sur l'année, tu me
rends Y % ». Ce montant n'existe nulle part dans les factures : il se calcule
sur les réceptions de la période, et se matérialise par un AVOIR fournisseur.

INVARIANT SERVEUR : un accord ne peut générer qu'UN SEUL avoir. Sans cette
garde, un double clic vaut un double crédit — la contrainte partielle
``avoir_genere`` unique par accord la rend impossible même en course.
"""
from django.db import models

from core.models import TenantModel


class AccordRFAFournisseur(TenantModel):
    """Accord de remise arrière annuelle avec un fournisseur."""

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        CLOS = 'clos', 'Clos'

    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.PROTECT,  # on_delete: PROTECT — un accord commercial NÉGOCIÉ (donnée réelle non reconstructible) ; on refuse la suppression du fournisseur plutôt que d'effacer l'accord
        related_name='accords_rfa')
    periode_debut = models.DateField()
    periode_fin = models.DateField()
    seuil_ca_achat = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="CA d'achat (HT) à atteindre pour déclencher la remise. "
                  '0 = remise due dès le premier dirham.')
    taux_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Remise en % du CA réalisé (exclusif avec montant_fixe).')
    montant_fixe = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Remise forfaitaire (exclusif avec taux_pct).')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF)
    # L'avoir généré pour CETTE période — la garde d'idempotence.
    avoir_genere = models.ForeignKey(
        'stock.AvoirFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accord_rfa_source')
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Accord RFA fournisseur'
        verbose_name_plural = 'Accords RFA fournisseur'
        ordering = ['-periode_debut', '-id']
        constraints = [
            models.CheckConstraint(
                check=models.Q(periode_fin__gte=models.F('periode_debut')),
                name='stock_accordrfa_periode_coherente'),
            # Un seul accord par (société, fournisseur, période) : sans cette
            # unicité, deux accords jumeaux généreraient deux avoirs pour le
            # même CA.
            models.UniqueConstraint(
                fields=['company', 'fournisseur', 'periode_debut',
                        'periode_fin'],
                name='stock_accordrfa_co_fourn_periode_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_accordrfa_co_statut'),
        ]

    def __str__(self):
        return (f'RFA {self.fournisseur_id} '
                f'{self.periode_debut}→{self.periode_fin}')

    @property
    def avoir_deja_genere(self):
        return self.avoir_genere_id is not None
