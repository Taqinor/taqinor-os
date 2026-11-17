"""Agendas externes abonnés, ESSENTIEL (reference/donnees.md §2.20, A18-M4).

L'URL vaut une clé : jamais rendue en entier, jamais journalisée. Seul `hote` est montré. Les
événements ne sont JAMAIS en base (cache borné par adresse).
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.db import models

from apps.taches.choix import EtatAgendaExterne
from apps.taches.models.base import StrNeutreMixin
from core.models import TenantModel


def hote_de(url):
    """Hôte d'une adresse (minuscules), `''` si elle n'en a pas."""
    try:
        return (urlsplit(url or '').hostname or '')[:255]
    except ValueError:
        return ''


class AgendaExterne(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    url = models.CharField(max_length=500)
    hote = models.CharField(max_length=255, editable=False)
    libelle = models.CharField(max_length=60, blank=True, default='')
    actif = models.BooleanField(default=True)
    rang = models.IntegerField(default=0)
    dernier_chargement_le = models.DateTimeField(null=True, blank=True)
    dernier_etat = models.CharField(max_length=20, choices=EtatAgendaExterne.choices, blank=True, default='')

    class Meta:
        verbose_name = 'agenda externe'
        verbose_name_plural = 'agendas externes'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'url'], name='taches_agext_url_uniq'),
        ]

    def save(self, *args, **kwargs):
        self.hote = hote_de(self.url)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'url' in update_fields and 'hote' not in update_fields:
            kwargs['update_fields'] = [*update_fields, 'hote']
        super().save(*args, **kwargs)
