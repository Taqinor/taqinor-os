# XMKT22 - fenetre de sunset d'engagement (jours). Additif : NULL =
# desactive (comportement actuel, aucun contact jamais marque dormant).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0050_xmkt7_pression_marketing"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="sunset_fenetre_jours",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text=(
                    "Fenêtre (jours, 90-180 typiquement) sans ouverture/clic "
                    "au-delà de laquelle un contact est marqué dormant et "
                    "sauté aux envois. Vide = désactivé (comportement "
                    "actuel)."),
            ),
        ),
    ]
