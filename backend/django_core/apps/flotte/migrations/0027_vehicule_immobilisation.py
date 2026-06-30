# Generated for FLOTTE30 — amortissement (lien immobilisations comptables).
# Ajoute le FK ``Vehicule.immobilisation`` → ``compta.Immobilisation`` (référencé
# par chaîne, jamais un import croisé des modèles compta). null = véhicule non
# rattaché. L'amortissement (VNC) est LU au travers des sélecteurs de
# ``apps.compta`` ; la flotte n'écrit jamais le module comptable. Additif,
# multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0003_immobilisation"),
        ("flotte", "0026_trajetchantier"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicule",
            name="immobilisation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="vehicules_flotte",
                to="compta.immobilisation",
                verbose_name="Immobilisation comptable",
            ),
        ),
    ]
