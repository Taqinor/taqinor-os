# ZMFG5 — Onglet « Instructions » structuré sur le ticket (mode opératoire),
# distinct de `description` (problème signalé) et du chatter `TicketActivity`.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0041_zmfg2_categorie_equipement'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='instructions',
            field=models.TextField(blank=True, default=''),
        ),
    ]
