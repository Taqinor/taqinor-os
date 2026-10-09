"""ASAV19 — échéance SLA de première réponse (champ additif nullable)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0068_asav13_reponse_type_statut'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='sla_reponse_due_at',
            field=models.DateField(blank=True, null=True),
        ),
    ]
