# XPUR26 — préparation mandat DGI 2026 e-facturation ENTRANT. Additif : flag
# société (défaut OFF, no-op) + champs clearance/conformité sur
# FactureFournisseur (défaut = non applicable, comportement historique
# inchangé pour toute facture existante ou saisie manuellement).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0052_xpos9_produit_suivi_serie"),
    ]

    operations = [
        migrations.AddField(
            model_name="achatsparametres",
            name="einvoicing_entrant_actif",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="numero_clearance_dgi",
            field=models.CharField(
                blank=True, max_length=100, null=True,
                help_text="Numéro de clearance DGI (e-invoicing entrant, si "
                          'fourni par le document UBL).'),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="statut_conformite_dgi",
            field=models.CharField(
                choices=[
                    ("non_applicable", "Non applicable"),
                    ("cleared", "Validée (clearance DGI)"),
                    ("non_cleared", "Non validée"),
                ],
                default="non_applicable", max_length=20),
        ),
    ]
