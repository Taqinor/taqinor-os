# NTRET5 — Arrhes / acompte sur commande comptoir (article en rupture ou
# sur-mesure). Additif : NULL/False = comportement historique inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0005_ntret3_codepincaissier"),
    ]

    operations = [
        migrations.AddField(
            model_name="ventecomptoir",
            name="montant_arrhes",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                help_text="Montant des arrhes encaissé (NTRET5). NULL = pas d'arrhes."),
        ),
        migrations.AddField(
            model_name="ventecomptoir",
            name="marchandise_remise",
            field=models.BooleanField(
                default=False,
                help_text="NTRET5 — la marchandise a été remise au client (solde "
                          "réglé, ou override admin journalisé). Indépendant du "
                          "statut : un override peut la poser à True alors que le "
                          "statut reste EN_ATTENTE_SOLDE (solde toujours dû)."),
        ),
        migrations.AlterField(
            model_name="ventecomptoir",
            name="statut",
            field=models.CharField(
                choices=[
                    ("brouillon", "Brouillon"),
                    ("validee", "Validée"),
                    ("annulee", "Annulée"),
                    ("en_attente_solde", "En attente de solde (arrhes)"),
                ],
                default="brouillon", max_length=20),
        ),
    ]
