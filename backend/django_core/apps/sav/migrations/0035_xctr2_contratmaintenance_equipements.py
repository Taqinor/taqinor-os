# XCTR2 — Registre des équipements couverts par un contrat de maintenance.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0034_zsav8_lead_id_ext'),
    ]

    operations = [
        migrations.AddField(
            model_name='contratmaintenance',
            name='equipements',
            field=models.ManyToManyField(
                blank=True, related_name='contrats_maintenance',
                to='sav.equipement',
                help_text='Équipements du parc couverts par ce contrat '
                          '(optionnel).',
                verbose_name='Équipements couverts'),
        ),
    ]
