"""NTMOB8 — préférence de notification PUSH par catégorie d'événement.

Additive : nouvelle colonne ``push`` (BooleanField, défaut True) sur
``NotificationPreference``. Défaut True = comportement historique inchangé
(le push partait déjà pour tout événement dès qu'un abonnement device N92
existait, sans distinction de catégorie) ; désactiver la catégorie côté
utilisateur devient possible sans dupliquer l'opt-in device global.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Renumérotée 0044 -> 0045 à l'intégration : une lane soeur (NTIDE52)
        # avait déjà pris 0044 sur cette app.
        ('notifications', '0044_ntide52_idea_email_events'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationpreference',
            name='push',
            field=models.BooleanField(default=True),
        ),
    ]
