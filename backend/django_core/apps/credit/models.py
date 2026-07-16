"""apps.credit — Gestion du crédit client (Groupe NTCRD).

Additif — ne modifie AUCUN modèle ventes/crm existant ; toutes les
références vers Client/Devis/BonCommande se font en string-FK
('crm.Client', 'ventes.Devis', 'ventes.BonCommande').
"""
from django.conf import settings
from django.db import models


class LimiteCredit(models.Model):
    """NTCRD2 — limite de crédit (encours max autorisé) par client.

    Un client SANS ``LimiteCredit`` (ou avec ``montant_limite=None``) n'a
    aucune limite définie : comportement actuel inchangé (aucun hold). Une
    entrée par (société, client) — ``unique_together``."""

    class ModeHold(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        AVERTISSEMENT = 'avertissement', 'Avertissement'
        BLOCAGE = 'blocage', 'Blocage'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='limites_credit')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,
        related_name='limites_credit')
    # NULL = pas de limite définie pour ce client (aucun blocage n'est
    # jamais déclenché — comportement historique inchangé).
    montant_limite = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Limite de crédit')
    devise = models.CharField(max_length=3, default='MAD')
    mode_hold = models.CharField(
        max_length=20, choices=ModeHold.choices, default=ModeHold.AVERTISSEMENT)
    actif = models.BooleanField(default=True)
    motif_null = models.TextField(
        blank=True, default='',
        help_text='Motif si la limite est volontairement non définie.')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='limites_credit_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Limite de crédit'
        verbose_name_plural = 'Limites de crédit'
        unique_together = [('company', 'client')]
        ordering = ['-date_modification']

    def __str__(self):
        return f'{self.client_id} — {self.montant_limite} {self.devise}'
