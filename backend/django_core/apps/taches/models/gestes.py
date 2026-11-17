"""L'UNIQUE mécanisme d'annulation (reference/donnees.md §2.15, §4, A7). Purge à 7 jours."""
from django.conf import settings
from django.db import models

from apps.taches.models.base import StrNeutreMixin
from core.models import TenantModel


class GesteAnnulable(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    type = models.CharField(max_length=24)
    message = models.CharField(max_length=200)
    operations = models.JSONField(default=list, blank=True)
    annule_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'geste annulable'
        verbose_name_plural = 'gestes annulables'
        indexes = [
            models.Index(fields=['company', 'proprietaire', 'created_at'], name='taches_geste_date_idx'),
        ]
