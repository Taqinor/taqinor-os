"""
FG307 — Attestations & assurances obligatoires des sous-traitants chantier.

``AttestationSousTraitant`` enregistre les pièces administratives qu'un
sous-traitant (``SousTraitant``, FG304) doit fournir pour être affecté à un
chantier au Maroc : attestation CNSS, assurance RC décennale, agrément métier,
attestation fiscale, etc. Chaque pièce porte une ``date_expiration`` ; une pièce
expirée (ou manquante) doit BLOQUER l'affectation du sous-traitant.

La logique de blocage est exposée en lecture seule via ``selectors.
sous_traitant_affectable`` (cross-app safe) et n'altère AUCUNE table existante :
elle se contente de lire l'état des attestations. Couche INDÉPENDANTE des statuts
de l'OS.

Additif & multi-tenant : on AJOUTE une table avec une FK ``company`` posée côté
serveur, jamais lue du corps de la requête.
"""
from django.conf import settings
from django.db import models


class AttestationSousTraitant(models.Model):
    """FG307 — pièce administrative obligatoire d'un sous-traitant (CNSS, RC
    décennale, agrément…), avec date d'expiration. Une pièce expirée bloque
    l'affectation.

    Multi-tenant : la société est posée côté serveur."""

    class Type(models.TextChoices):
        CNSS = 'cnss', 'Attestation CNSS'
        RC_DECENNALE = 'rc_decennale', 'Assurance RC décennale'
        RC_TRAVAUX = 'rc_travaux', 'Assurance RC travaux'
        AGREMENT = 'agrement', 'Agrément métier'
        FISCALE = 'fiscale', 'Attestation fiscale'
        AUTRE = 'autre', 'Autre pièce'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_attestations_sous_traitant')
    sous_traitant = models.ForeignKey(
        'installations.SousTraitant', on_delete=models.CASCADE,
        related_name='attestations')
    # max_length=20 couvre le plus long code de Type ('rc_decennale' = 12).
    type_piece = models.CharField(
        max_length=20, choices=Type.choices, default=Type.AUTRE)
    # Numéro de la pièce / police d'assurance tel que fourni.
    reference = models.CharField(max_length=120, blank=True, null=True)
    organisme = models.CharField(max_length=255, blank=True, null=True)
    date_emission = models.DateField(null=True, blank=True)
    # Date d'expiration : une pièce expirée (ou sans date) bloque l'affectation.
    date_expiration = models.DateField(null=True, blank=True)
    # Pièce obligatoire pour l'affectation (sinon simple information).
    obligatoire = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_attestations_sous_traitant_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Attestation sous-traitant'
        verbose_name_plural = 'Attestations sous-traitant'
        ordering = ['sous_traitant_id', 'type_piece']
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'sous_traitant'],
                         name='idx_att_co_soustrait'),
            models.Index(fields=['company', 'date_expiration'],
                         name='idx_att_co_expiration'),
        ]

    def __str__(self):
        return f'{self.get_type_piece_display()} · {self.sous_traitant_id}'

    def est_valide(self, a_la_date=None):
        """Vrai si la pièce est encore valide à la date donnée (aujourd'hui par
        défaut). Une pièce sans date d'expiration est considérée valide
        (pièce sans échéance, ex. agrément permanent)."""
        from django.utils import timezone
        if self.date_expiration is None:
            return True
        ref = a_la_date or timezone.now().date()
        return self.date_expiration >= ref
