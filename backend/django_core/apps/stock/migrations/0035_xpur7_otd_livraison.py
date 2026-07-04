# XPUR7 — Dates de livraison prévues, accusé fournisseur & OTD réel.
# Additif : PrixFournisseur.delai_livraison_jours (null), BonCommandeFournisseur
# .date_livraison_prevue / date_confirmee_fournisseur /
# numero_confirmation_fournisseur (tous null/vide = comportement historique).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0034_xpur6_conditions_paiement"),
    ]

    operations = [
        migrations.AddField(
            model_name="prixfournisseur",
            name="delai_livraison_jours",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="date_livraison_prevue",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="date_confirmee_fournisseur",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="numero_confirmation_fournisseur",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
