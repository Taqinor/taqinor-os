"""NTP2P37 — séparation des tâches (SoD) demandeur ≠ approbateur.

Additif pur : un interrupteur ``AchatsParametres.sod_stricte`` à ``False``.
Sans activation, un créateur peut encore approuver sa propre demande —
comportement historique des structures à un seul décideur.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0097_ntp2p7_onboarding_fournisseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='achatsparametres',
            name='sod_stricte',
            field=models.BooleanField(default=False),
        ),
    ]
