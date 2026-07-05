# ZMFG12 — Motif de mise au rebut d'un équipement + statut « au rebut » dans
# le parc. `mis_au_rebut`/`date_rebut`/`motif_rebut`, additifs, défaut inactif
# (False) = comportement actuel inchangé pour le parc existant.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0042_zmfg5_ticket_instructions'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipement',
            name='mis_au_rebut',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='equipement',
            name='date_rebut',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='equipement',
            name='motif_rebut',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
