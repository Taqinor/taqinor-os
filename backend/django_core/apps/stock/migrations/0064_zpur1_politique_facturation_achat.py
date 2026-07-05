# ZPUR1 — Politique de facturation d'achat par produit (à la commande vs à
# la réception, parité Odoo « Bill Control »). Additif : défaut
# sur_reception = comportement historique inchangé (FG56 seul chemin).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0063_yproc10_chantier_origine_bcf"),
    ]

    operations = [
        migrations.AddField(
            model_name="produit",
            name="politique_facturation_achat",
            field=models.CharField(
                choices=[
                    ("sur_reception", "Sur réception"),
                    ("sur_commande", "Sur commande"),
                ],
                default="sur_reception",
                max_length=20,
                verbose_name="Politique de facturation d'achat"),
        ),
    ]
