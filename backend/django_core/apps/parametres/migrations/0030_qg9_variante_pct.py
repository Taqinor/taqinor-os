# QG9 — pourcentage configurable des variantes de devis (défaut 20 %).
# Additif : nouveau champ nullable-par-défaut (valeur par défaut 20) sur
# CompanyProfile ; aucune donnée existante touchée.
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0029_translationoverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="variante_pct",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("20"),
                help_text="Pourcentage des variantes de devis (échelles "
                          "1−p / 1 / 1+p). Défaut 20 %.",
                max_digits=5,
            ),
        ),
    ]
