"""Présence hors de l'ERP : jetons d'accès et coupe-circuit de la société
(reference/donnees.md §2.14, §2.21).

Jamais de jeton en clair en base : `jeton_hash` = SHA-256 hex ; un seul jeton actif par usage.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.taches.choix import UsageJeton
from apps.taches.models.base import StrNeutreMixin
from core.models import TenantModel


class JetonAcces(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: suit le compte
    usage = models.CharField(max_length=10, choices=UsageJeton.choices)
    prefixe = models.CharField(max_length=8)
    jeton_hash = models.CharField(max_length=64, unique=True)
    libelle = models.CharField(max_length=60, blank=True, default='')
    dernier_usage_le = models.DateTimeField(null=True, blank=True)
    revoque_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "jeton d'accès"
        verbose_name_plural = "jetons d'accès"
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'proprietaire', 'usage'],
                condition=Q(revoque_le__isnull=True),
                name='taches_jeton_actif_uniq'),
        ]


class ReglagesSociete(StrNeutreMixin, TenantModel):
    """Coupe-circuit par société (A18-M8) ; absent = actif. Écrit par un administrateur seul."""

    balayage_actif = models.BooleanField(default=True)
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,  # on_delete: trace gardée si le compte disparaît
        null=True, blank=True, related_name='+')
    modifie_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'réglages de la société'
        verbose_name_plural = 'réglages de la société'
        constraints = [
            models.UniqueConstraint(fields=['company'], name='taches_regsoc_uniq'),
        ]
