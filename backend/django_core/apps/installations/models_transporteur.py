"""
FG331 — Transporteurs & tarifs de transport.

Un `Transporteur` est un prestataire d'acheminement (interne ou tiers) avec un
contact et un tarif de base. Une `Livraison` (FG329) peut lui être affectée et
porter un coût de course (`cout_transport`). Ce coût est INTERNE (jamais
client-facing).

Cross-app : aucun. Additif & multi-tenant : FK `company` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class Transporteur(models.Model):
    """FG331 — transporteur (interne ou tiers) avec un tarif de base indicatif.

    Multi-tenant : société posée côté serveur. ``tarif_base`` est un coût de
    référence (INTERNE) ; le coût réel d'une course est porté par la livraison."""

    class Type(models.TextChoices):
        INTERNE = 'interne', 'Interne'
        TIERS = 'tiers', 'Tiers'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_transporteurs')
    nom = models.CharField(max_length=255)
    type_transporteur = models.CharField(
        max_length=20, choices=Type.choices, default=Type.TIERS)
    contact = models.CharField(max_length=255, blank=True, null=True)
    telephone = models.CharField(max_length=40, blank=True, null=True)
    tarif_base = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_transporteurs_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transporteur'
        verbose_name_plural = 'Transporteurs'
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        indexes = [
            models.Index(fields=['company', 'active'],
                         name='idx_transp_co_active'),
        ]

    def __str__(self):
        return self.nom
