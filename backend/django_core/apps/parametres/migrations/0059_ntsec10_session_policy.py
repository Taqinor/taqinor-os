# Generated for NTSEC10 — politique de session par société (additif, inerte).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0058_unitemesure'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='session_absolute_hours',
            field=models.PositiveIntegerField(default=0, help_text="Durée de vie absolue d'une session (heures) depuis sa création. 0 = durée JWT actuelle (défaut)."),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='session_idle_minutes',
            field=models.PositiveIntegerField(default=0, help_text="Délai d'inactivité (minutes) au-delà duquel une session ne peut plus rafraîchir. 0 = désactivé (défaut)."),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='max_concurrent_sessions',
            field=models.PositiveIntegerField(default=0, help_text="Nombre maximum de sessions concurrentes par utilisateur (la plus ancienne est révoquée au-delà). 0 = illimité."),
        ),
    ]
