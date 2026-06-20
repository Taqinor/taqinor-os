# Le reporting agrège les modèles des autres apps — historiquement aucun modèle
# propre. N79 introduit le SEUL modèle de l'app : un rapport sauvegardé,
# programmable, dont l'envoi par email est piloté par Celery Beat.
from django.conf import settings
from django.db import models


class SavedReport(models.Model):
    """N79 — Rapport sauvegardé + planification d'envoi par email.

    Multi-tenant : `company` est posée CÔTÉ SERVEUR (jamais lue du corps de
    requête) ; toutes les requêtes sont bornées à la société de l'utilisateur.
    `definition` (JSON) porte les paramètres du rapport (période, filtres…) ;
    `target_kind` choisit quel rapport rendre. `schedule` décide de la cadence
    d'envoi automatique. ADDITIF : NULL/valeurs par défaut = inerte
    (`schedule='none'` → la tâche planifiée ne l'envoie jamais)."""

    class TargetKind(models.TextChoices):
        SALES = 'sales', 'Ventes'
        STOCK = 'stock', 'Stock'
        SERVICE = 'service', 'Service'

    class Schedule(models.TextChoices):
        NONE = 'none', 'Aucune'
        DAILY = 'daily', 'Quotidien'
        WEEKLY = 'weekly', 'Hebdomadaire'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='saved_reports')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='saved_reports')
    name = models.CharField(max_length=255)
    # Paramètres du rapport (période/filtres). Forme libre, défaut objet vide.
    definition = models.JSONField(default=dict, blank=True)
    target_kind = models.CharField(
        max_length=20, choices=TargetKind.choices, default=TargetKind.SALES)
    schedule = models.CharField(
        max_length=10, choices=Schedule.choices, default=Schedule.NONE)
    # Destinataires : une ou plusieurs adresses (séparées par virgule/point-virgule
    # ou retour à la ligne). Vide → aucun envoi (NO-OP).
    recipients = models.TextField(blank=True, default='')
    # Dernier envoi réussi (anti-doublon léger / traçabilité). NULL = jamais.
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rapport sauvegardé'
        verbose_name_plural = 'Rapports sauvegardés'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'schedule']),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_target_kind_display()})'

    def recipient_list(self):
        """Adresses email destinataires, nettoyées. Liste vide si aucune."""
        raw = self.recipients or ''
        parts = []
        for chunk in raw.replace(';', ',').replace('\n', ',').split(','):
            addr = chunk.strip()
            if addr:
                parts.append(addr)
        return parts
