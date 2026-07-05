# XCTR1 — Produit recurrent (abonnement) -> conversion auto en contrat de
# maintenance a l'acceptation d'un devis. Additif : est_recurrent=False et
# periodicite_defaut=NULL preservent le comportement historique de tout
# produit existant.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0065_zpur3_modele_bcf"),
    ]

    operations = [
        migrations.AddField(
            model_name="produit",
            name="est_recurrent",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Prestation d'abonnement (maintenance, monitoring…) : une "
                    "ligne de ce produit sur un devis accepté crée "
                    "automatiquement un contrat de maintenance SAV."
                ),
                verbose_name="Produit récurrent (abonnement)",
            ),
        ),
        migrations.AddField(
            model_name="produit",
            name="periodicite_defaut",
            field=models.CharField(
                blank=True,
                choices=[
                    ("mensuel", "Mensuel"),
                    ("trimestriel", "Trimestriel"),
                    ("semestriel", "Semestriel"),
                    ("annuel", "Annuel"),
                ],
                help_text=(
                    "Périodicité proposée au contrat de maintenance créé "
                    "(vide = annuel)."
                ),
                max_length=15,
                null=True,
                verbose_name="Périodicité par défaut",
            ),
        ),
    ]
