# Generated for WIR90 — liens optionnels vers stock.Fournisseur (Garage,
# ContratVehicule) : id numérique référencé, jamais un FK cross-app dur.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flotte', '0057_vehicule_custom_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='garage',
            name='fournisseur_id_ref',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Fournisseur (référentiel stock)'),
        ),
        migrations.AddField(
            model_name='contratvehicule',
            name='fournisseur_id_ref',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Fournisseur (référentiel stock)'),
        ),
    ]
