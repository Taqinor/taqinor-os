# ZPUR7 — brouillon de relance programme + compteur pour les BCF en retard.
# Additif : `nb_relances` (defaut 0) sur BonCommandeFournisseur et
# `relance_bcf_actif` (defaut False = OFF, no-op) sur AchatsParametres.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0067_xstk13_inventaireannuel_donnees_encoder"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="nb_relances",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="achatsparametres",
            name="relance_bcf_actif",
            field=models.BooleanField(default=False),
        ),
    ]
