"""N75 — préférences de notification in-app par utilisateur et par évènement.

Le reporting agrège surtout les modèles des autres apps ; ce seul modèle stocke,
par utilisateur, l'activation in-app de chaque TYPE d'évènement de la cloche de
notifications. Absence de ligne = activé (défaut : tout s'affiche, comportement
historique inchangé). L'envoi sortant WhatsApp/email/SMS reste gated (G1/G2/G9) ;
ce modèle ne couvre que le canal in-app.
"""
from django.conf import settings
from django.db import models


# Types d'évènement de la cloche (clés stables = clés du payload notifications).
NOTIF_EVENT_TYPES = [
    ('activites_en_retard', 'Activités en retard'),
    ('garanties_expirantes', 'Garanties expirant bientôt'),
    ('factures_impayees', 'Factures impayées / en retard'),
    ('chantiers_a_planifier', 'Chantiers à planifier / poser'),
    ('maintenance_due', 'Visites de maintenance dues'),
    ('tickets_ouverts', 'Tickets SAV ouverts'),
    ('stock_bas', 'Stock bas'),
]
NOTIF_EVENT_KEYS = [k for k, _ in NOTIF_EVENT_TYPES]


class NotificationPreference(models.Model):
    """Préférence in-app d'un utilisateur pour un type d'évènement. Une ligne
    n'existe que lorsqu'un type est explicitement DÉSACTIVÉ (in_app=False) ou
    réactivé ; sans ligne, le type est considéré activé."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notification_preferences')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notification_preferences')
    event_type = models.CharField(max_length=40, choices=NOTIF_EVENT_TYPES)
    in_app = models.BooleanField(default=True)

    class Meta:
        unique_together = [('user', 'event_type')]
        verbose_name = 'Préférence de notification'
        verbose_name_plural = 'Préférences de notification'

    def __str__(self):
        return f"{self.user_id} · {self.event_type} · {'on' if self.in_app else 'off'}"
