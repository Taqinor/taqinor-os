# ZMKT3 - etoiler une campagne comme modele reutilisable (est_modele).
# Additif : defaut False = comportement actuel (aucune campagne n'est un
# modele tant que non explicitement etoilee).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0093_zmkt1_campagne_statuts_pipeline"),
    ]

    operations = [
        migrations.AddField(
            model_name="campagne",
            name="est_modele",
            field=models.BooleanField(
                default=False,
                verbose_name="Modèle réutilisable (jamais envoyé)"),
        ),
    ]
