"""Journal d'audit des paramètres (``SettingsAuditLog``) — N55.

Domaine « Avancé / Journal d'audit ». Extrait de l'ancien ``models.py`` sans
aucun changement de champ, de ``Meta`` ou de nom de table — la table reste
``parametres_settingsauditlog`` (split sans migration)."""
from django.conf import settings
from django.db import models


class SettingsAuditLog(models.Model):
    """Une ligne par changement de paramètre (company-scopée) — N55.

    `section` regroupe les changements (ex. 'profil', 'messages') et `field`
    nomme le champ modifié. `old_value`/`new_value` sont stockés en texte
    (str() de la valeur). Aucune donnée de prix d'achat / marge n'est concernée
    par les paramètres."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='settings_audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settings_audit_logs',
    )
    section = models.CharField(max_length=50, default='profil')
    field = models.CharField(max_length=100, blank=True, default='')
    field_label = models.CharField(max_length=150, blank=True, default='')
    old_value = models.TextField(blank=True, default='')
    new_value = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Journal d'audit des paramètres"
        verbose_name_plural = "Journaux d'audit des paramètres"

    def __str__(self):
        return f'{self.section}.{self.field} @ {self.timestamp:%Y-%m-%d %H:%M}'

    @classmethod
    def log_change(cls, company, user, section, field, field_label, old, new):
        """Écrit une ligne d'audit (ancien→nouveau) en texte."""
        return cls.objects.create(
            company=company,
            user=user if (user and getattr(
                user, 'is_authenticated', False)) else None,
            section=section,
            field=field or '',
            field_label=field_label or '',
            old_value='' if old is None else str(old),
            new_value='' if new is None else str(new),
        )
