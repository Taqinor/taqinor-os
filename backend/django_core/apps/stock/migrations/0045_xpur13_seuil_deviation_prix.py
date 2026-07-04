# XPUR13 — Garde-fous prix sur la ligne BCF : seuil d'écart % (paramétrable
# par société) au-delà duquel une ligne de BCF lève un warning « prix hors
# norme » vs le dernier prix/prix moyen d'achat. Additif : 0 = comportement
# historique inchangé (aucun seuil, pas de warning d'écart).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0041_xctr17_produit_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="achatsparametres",
            name="seuil_deviation_prix_pct",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=5,
                help_text=(
                    "Écart %% (vs dernier prix/prix moyen) déclenchant un "
                    "warning sur une ligne de BCF. 0 = désactivé."
                ),
            ),
        ),
    ]
