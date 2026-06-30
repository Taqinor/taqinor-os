"""
FG306 — Factures & règlements des sous-traitants chantier (comptes à payer
dédiés à la main-d'œuvre sous-traitée).

``FactureSousTraitant`` est la facture ENTRANTE émise par un sous-traitant de
l'annuaire (``SousTraitant``, FG304), rattachée à un ordre de travaux
(``OrdreSousTraitance``, FG305) ou directement au sous-traitant. C'est le pendant
« main-d'œuvre » des comptes à payer matériel (``stock.FactureFournisseur``) :
distinct, car on ne facture pas du panneau ici mais une prestation de pose/travaux.

``PaiementSousTraitant`` enregistre les règlements (acomptes, soldes) imputés sur
une facture sous-traitant. Le RESTE À PAYER est dérivé (montant TTC − Σ paiements).

Tous ces montants sont des données INTERNES : ils ne paraissent JAMAIS sur un
document destiné au client (devis, facture client, proposition). Couche de statut
PROPRE (brouillon → à payer → partiellement payée → payée → annulée), distincte
des trois couches de l'OS (entonnoir ``STAGES.py``, statut document ventes, statut
chantier).

Additif & multi-tenant : on AJOUTE des tables avec une FK ``company`` posée côté
serveur, jamais lue du corps de la requête. ``sous_traitant`` / ``ordre`` /
``chantier`` sont validés tenant (même société) côté vue.
"""
from django.conf import settings
from django.db import models


class FactureSousTraitant(models.Model):
    """FG306 — facture entrante d'un sous-traitant chantier (compte à payer
    main-d'œuvre), DISTINCTE d'une facture fournisseur matériel.

    Multi-tenant : la société est posée côté serveur. Le ``statut`` suit le cycle
    de vie de la facture (brouillon → à payer → partiellement/entièrement payée →
    annulée), distinct de toute autre couche de statut de l'OS. Les montants sont
    INTERNES — jamais client-facing."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        A_PAYER = 'a_payer', 'À payer'
        PARTIELLE = 'partielle', 'Partiellement payée'
        PAYEE = 'payee', 'Payée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_factures_sous_traitant')
    # Numéro de la facture tel qu'émis PAR le sous-traitant (pièce reçue).
    numero = models.CharField(max_length=80, blank=True, null=True)
    sous_traitant = models.ForeignKey(
        'installations.SousTraitant', on_delete=models.PROTECT,
        related_name='installations_factures')
    # Ordre de travaux rattaché (optionnel : une facture peut couvrir un ordre
    # précis ou être hors-ordre). SET_NULL : on ne perd pas la facture si l'ordre
    # disparaît.
    ordre = models.ForeignKey(
        'installations.OrdreSousTraitance', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='factures')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_factures_sous_traitant')
    # Montants INTERNES (MAD). DecimalField : jamais de flottant sur de l'argent.
    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    montant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    date_facture = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    # max_length=20 couvre le plus long code de Statut ('partielle' = 9).
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_factures_sous_traitant_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Facture sous-traitant'
        verbose_name_plural = 'Factures sous-traitant'
        ordering = ['-date_creation']
        indexes = [
            # Noms d'index ≤ 30 caractères (contrainte Django/Postgres).
            models.Index(fields=['company', 'statut'],
                         name='idx_fst_co_statut'),
            models.Index(fields=['company', 'sous_traitant'],
                         name='idx_fst_co_soustrait'),
        ]

    def __str__(self):
        return f'{self.numero or self.id} · {self.sous_traitant_id}'

    @property
    def total_paye(self):
        """Σ des paiements imputés (INTERNE)."""
        from decimal import Decimal
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

    @property
    def reste_a_payer(self):
        """Reste à payer = TTC − Σ paiements (jamais négatif). INTERNE."""
        from decimal import Decimal
        reste = (self.montant_ttc or Decimal('0')) - self.total_paye
        return reste if reste > 0 else Decimal('0')


class PaiementSousTraitant(models.Model):
    """FG306 — règlement (acompte/solde) imputé sur une facture sous-traitant.

    Multi-tenant : la société est posée côté serveur. Le montant est INTERNE —
    jamais client-facing."""

    class Mode(models.TextChoices):
        VIREMENT = 'virement', 'Virement'
        CHEQUE = 'cheque', 'Chèque'
        ESPECES = 'especes', 'Espèces'
        EFFET = 'effet', 'Effet / traite'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_paiements_sous_traitant')
    facture = models.ForeignKey(
        FactureSousTraitant, on_delete=models.CASCADE,
        related_name='paiements')
    montant = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_paiement = models.DateField(null=True, blank=True)
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.VIREMENT)
    reference_paiement = models.CharField(max_length=120, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_paiements_sous_traitant_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement sous-traitant'
        verbose_name_plural = 'Paiements sous-traitant'
        ordering = ['-date_paiement', '-id']
        indexes = [
            models.Index(fields=['company', 'facture'],
                         name='idx_pst_co_facture'),
        ]

    def __str__(self):
        return f'{self.montant} · {self.facture_id}'
