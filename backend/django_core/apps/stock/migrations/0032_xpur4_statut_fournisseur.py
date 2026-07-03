# XPUR4 — Statuts fournisseur actif / bloqué commandes / bloqué paiements.
# Additif : Fournisseur.statut (défaut 'actif' = comportement historique
# inchangé pour tous les fournisseurs existants) + motif_blocage.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0031_xpur3_multidevises_achats"),
    ]

    operations = [
        migrations.AddField(
            model_name="fournisseur",
            name="statut",
            field=models.CharField(
                choices=[
                    ("actif", "Actif"),
                    ("bloque_commandes", "Bloqué (commandes)"),
                    ("bloque_paiements", "Bloqué (paiements)"),
                    ("bloque_total", "Bloqué (total)"),
                ],
                default="actif", max_length=20,
                help_text='Statut fournisseur : actif, bloqué commandes, '
                          'bloqué paiements ou bloqué total.',
            ),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="motif_blocage",
            field=models.TextField(blank=True, null=True),
        ),
    ]
