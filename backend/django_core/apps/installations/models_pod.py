"""
FG330 — Preuve de livraison (POD).

À la remise sur site, FG330 capture la PREUVE de livraison rattachée à une
`Livraison` (FG329) : nom + signature du destinataire, photo de la remise
(`records.Attachment`), position GPS et horodatage. Une seule preuve par
livraison.

Cross-app : `records.Attachment` est une app foundation (exemptée). `Livraison`
est du MÊME app (FK directe). Additif & multi-tenant : FK `company` posée côté
serveur.
"""
from django.conf import settings
from django.db import models


class PreuveLivraison(models.Model):
    """FG330 — preuve de livraison (signature + photo + GPS horodaté).

    Multi-tenant : société posée côté serveur. ``livraison`` est en OneToOne :
    une seule preuve par livraison. ``signature_data`` stocke une signature
    vectorielle/base64 légère (texte), la photo passe par `records.Attachment`."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_preuves_livraison')
    livraison = models.OneToOneField(
        'installations.Livraison', on_delete=models.CASCADE,
        related_name='preuve')
    signataire_nom = models.CharField(max_length=255, blank=True, null=True)
    signature_data = models.TextField(blank=True, null=True)
    photo = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    horodatage = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_preuves_livraison_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Preuve de livraison'
        verbose_name_plural = 'Preuves de livraison'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'livraison'],
                         name='idx_pod_co_livraison'),
        ]

    def __str__(self):
        return f'POD {self.livraison_id} · {self.signataire_nom or "—"}'
