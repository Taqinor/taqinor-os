# Generated for FLOTTE3 — lien Vehicule -> stock.EmplacementStock (id numérique).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0002_enginroulant"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicule",
            name="emplacement_stock_id",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Emplacement de stock (id)",
            ),
        ),
    ]
