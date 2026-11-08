"""AAPV20 — lot et numéros de série sur la ligne de retour fournisseur.
Additive (deux champs nullables), revertable."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0009_aapv5_ras_imputation_acompte'),
    ]

    operations = [
        migrations.AddField(
            model_name='ligneretourfournisseur',
            name='numero_lot',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='ligneretourfournisseur',
            name='numeros_serie',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
