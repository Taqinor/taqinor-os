# XSTK10 — flux de casse/mise au rebut : motifs additionnels sur
# MouvementStock.motif_rebut (obsolete/perime/vol), en plus des motifs XMFG11
# existants (casse/defaut/erreur/autre). Choices-only, aucune donnée
# existante affectée.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0056_xstk8_stock_negatif_autorise"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mouvementstock",
            name="motif_rebut",
            field=models.CharField(
                blank=True,
                choices=[
                    ("casse", "Casse"),
                    ("defaut", "Défaut"),
                    ("erreur", "Erreur"),
                    ("obsolete", "Obsolète"),
                    ("perime", "Périmé"),
                    ("vol", "Vol"),
                    ("autre", "Autre"),
                ],
                max_length=10, null=True),
        ),
    ]
