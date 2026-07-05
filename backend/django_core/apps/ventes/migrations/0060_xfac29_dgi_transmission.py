# XFAC29 — Facturation électronique DGI SORTANTE : champs de suivi de la
# transmission (statut/référence/motif de rejet). Additif, défaut =
# comportement actuel byte-identique tant qu'aucune transmission n'est
# déclenchée (interrupteur maître côté parametres.CompanyProfile, OFF).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0059_yledg5_paiement_rejete"),
    ]

    operations = [
        migrations.AddField(
            model_name="facture",
            name="dgi_statut",
            field=models.CharField(
                choices=[
                    ("a_transmettre", "À transmettre"),
                    ("transmise", "Transmise"),
                    ("acceptee", "Acceptée"),
                    ("rejetee", "Rejetée"),
                ],
                default="a_transmettre", max_length=15,
                verbose_name="Statut transmission DGI"),
        ),
        migrations.AddField(
            model_name="facture",
            name="dgi_reference",
            field=models.CharField(
                blank=True, default="", max_length=100,
                verbose_name="Référence DGI"),
        ),
        migrations.AddField(
            model_name="facture",
            name="dgi_motif_rejet",
            field=models.TextField(
                blank=True, default="", verbose_name="Motif de rejet DGI"),
        ),
    ]
