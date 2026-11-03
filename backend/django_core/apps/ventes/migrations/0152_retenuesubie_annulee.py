# AARG35 — une retenue à la source d'une facture annulée ne compte plus et n'attend
# plus d'attestation. Additif : défaut faux, aucune donnée réécrite.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0151_regles_calcul_niveau_11'),
    ]

    operations = [
        migrations.AddField(
            model_name='retenuesubie',
            name='annulee',
            field=models.BooleanField(default=False),
        ),
    ]
