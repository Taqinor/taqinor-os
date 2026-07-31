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
        ('notifications', '0043_ntedu40_education_reinscription_relance_event'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationpreference',
            name='push',
            field=models.BooleanField(default=True),
        ),
    ]
