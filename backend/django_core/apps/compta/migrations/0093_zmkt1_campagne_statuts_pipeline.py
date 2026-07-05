# ZMKT1 - statuts additifs de pipeline mailing (en_file/envoi_en_cours) sur
# Campagne.Statut. Additif : les choix existants (brouillon/envoyee/annulee)
# restent inchanges, seuls des choix supplementaires sont ajoutes.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0092_xmkt33_domaine_envoi"),
    ]

    operations = [
        migrations.AlterField(
            model_name="campagne",
            name="statut",
            field=models.CharField(
                choices=[
                    ("brouillon", "Brouillon"), ("en_file", "En file"),
                    ("envoi_en_cours", "Envoi en cours"),
                    ("envoyee", "Envoyée"), ("annulee", "Annulée"),
                ],
                default="brouillon", max_length=15, verbose_name="Statut"),
        ),
    ]
