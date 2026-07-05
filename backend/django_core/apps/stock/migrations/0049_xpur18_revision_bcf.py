# XPUR18 — Révision de BCF tracée + ré-approbation. Additif :
# BonCommandeFournisseur.revision (défaut 0 = jamais révisé, comportement
# historique inchangé, imprimé "Rév. N" seulement à partir de 1).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0048_xpur17_tva_ligne_facture_fournisseur"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="revision",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
