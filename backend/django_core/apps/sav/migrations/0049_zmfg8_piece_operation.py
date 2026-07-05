# ZMFG8 - Typage operationnel des pieces sur ticket : Ajout / Retrait /
# Recyclage. Additif : operation="retrait" par defaut sur PieceRetiree ->
# aucune ligne existante ne devient recyclage implicitement.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0048_zmfg7_categorie_alias_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="pieceretiree",
            name="operation",
            field=models.CharField(
                choices=[("retrait", "Retrait"), ("recyclage", "Recyclage")],
                default="retrait",
                help_text=(
                    "Retrait (rebut/RMA) ou recyclage (remise en circulation "
                    "— exige destination=stock_occasion)."
                ),
                max_length=10,
            ),
        ),
    ]
