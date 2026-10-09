"""ASAV21 — échéance SLA horodatée (heures ouvrées), champ additif nullable."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0069_asav19_sla_reponse_due_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='sla_echeance_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
