# XSAL1 — Client.liste_prix : tarif négocié (string-FK additive, nullable).
# Additive/reversible: no existing column changed.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0069_xsal1_listeprix'),
        ('crm', '0044_qw10_lead_dedup_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='liste_prix',
            field=models.ForeignKey(
                blank=True,
                help_text='Tarif négocié pour ce client. Vide = prix de vente standard.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='clients',
                to='ventes.listeprix',
                verbose_name='Liste de prix',
            ),
        ),
    ]
