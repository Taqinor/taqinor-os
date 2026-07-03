# XPUR2 — RAS-TVA sur paiements fournisseurs (LF 2024, en vigueur 01/07/2024).
# Additif : FactureFournisseur.type_achat (biens/services, défaut biens),
# PaiementFournisseur.montant_ras_tva/taux_ras (défaut 0), AchatsParametres.
# ras_tva_actif (défaut False = comportement historique inchangé).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0029_xpur1_conformite_fournisseur"),
    ]

    operations = [
        migrations.AddField(
            model_name="achatsparametres",
            name="ras_tva_actif",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="type_achat",
            field=models.CharField(
                choices=[
                    ("biens", "Biens & travaux"),
                    ("services", "Prestations de services"),
                ],
                default="biens", max_length=10,
                help_text="Nature de l'achat (RAS-TVA LF 2024) : biens & "
                          "travaux ou prestations de services.",
            ),
        ),
        migrations.AddField(
            model_name="paiementfournisseur",
            name="montant_ras_tva",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=14,
                help_text="Montant de la retenue à la source sur la TVA "
                          "(LF 2024).",
            ),
        ),
        migrations.AddField(
            model_name="paiementfournisseur",
            name="taux_ras",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=5,
                help_text="Taux de RAS-TVA appliqué (0/75/100 %).",
            ),
        ),
    ]
