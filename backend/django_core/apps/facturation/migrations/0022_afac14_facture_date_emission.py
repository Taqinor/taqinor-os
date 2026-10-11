"""AFAC14 (C-AFAC-005) — ``Facture.date_emission`` : ``auto_now_add`` →
``default=timezone.localdate``.

La date d'émission est désormais RE-posée par ``emettre_facture`` au passage
à ÉMISE (jour de l'émission, date locale), au lieu d'être figée à la création
du brouillon. ``auto_now_add`` écrasait toute valeur posée à la création, d'où
le changement de défaut. Aucune donnée réécrite (aucune facture re-datée),
aucun SQL de schéma (le défaut est appliqué par Django). Réversible : revenir
à facturation 0021.
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0021_atot36_avoir_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='facture',
            name='date_emission',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
    ]
