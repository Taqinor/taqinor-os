"""NTOBS6 — liens de téléchargement tokenisés expirant (helper GÉNÉRIQUE).

Même PRINCIPE que ``ged.PartageGed`` (jeton long imprévisible + expiration +
kill-switch), sans en dépendre (``core`` reste fondation, aucun import
d'``apps.ged``) : un helper dédié, réutilisable par n'importe quelle future
fonctionnalité ``core`` qui doit livrer un fichier MinIO via un lien
temporaire sans authentification (ex. NTOBS6 — export de réversibilité).

Modèle défini ICI (pas directement dans ``core/models.py``) et réexporté en
bas de ``core/models.py`` — même éclatement que ``core/sharing.py``/
``core/sla.py``.
"""
from __future__ import annotations

import secrets

from django.db import models
from django.utils import timezone

DEFAULT_EXPIRY_DAYS = 7


def _default_token():
    return secrets.token_urlsafe(32)


class SignedDownload(models.Model):
    """Jeton d'accès à UN objet MinIO, borné dans le temps.

    ``company`` posée côté serveur (jamais lue d'un corps de requête) — un
    jeton ne référence qu'UN objet d'UNE seule société. ``actif=False`` =
    révocation immédiate (kill-switch), sans attendre l'expiration."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='signed_downloads', verbose_name='Société')
    token = models.CharField(
        max_length=64, unique=True, default=_default_token)
    bucket = models.CharField('Bucket MinIO', max_length=100)
    object_key = models.CharField('Clé objet MinIO', max_length=500)
    taille_octets = models.BigIntegerField(
        'Taille (octets)', null=True, blank=True)
    expire_le = models.DateTimeField('Expire le')
    actif = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lien de téléchargement tokenisé'
        verbose_name_plural = 'Liens de téléchargement tokenisés'
        ordering = ['-created_at']

    def __str__(self):
        return f'SignedDownload {self.token[:8]}… ({self.bucket}/{self.object_key})'

    @property
    def expire(self):
        return timezone.now() >= self.expire_le


def creer_lien(company, bucket, object_key, taille_octets=None,
               expiry_days=DEFAULT_EXPIRY_DAYS):
    """Crée un jeton de téléchargement valide ``expiry_days`` jours."""
    return SignedDownload.objects.create(
        company=company, bucket=bucket, object_key=object_key,
        taille_octets=taille_octets,
        expire_le=timezone.now() + timezone.timedelta(days=expiry_days),
    )


def resoudre_lien(token):
    """(bucket, object_key) si le jeton est valide (actif, non expiré) —
    ``None`` sinon (jeton inconnu/révoqué/expiré, jamais une exception)."""
    try:
        lien = SignedDownload.objects.get(token=token)
    except SignedDownload.DoesNotExist:
        return None
    if not lien.actif or lien.expire:
        return None
    return lien.bucket, lien.object_key
