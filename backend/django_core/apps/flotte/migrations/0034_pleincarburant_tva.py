# Generated for XFLT8 — TVA carburant : récupérable vs non déductible. Ajoute
# des champs additifs sur ``PleinCarburant`` (tva_recuperable, montant_tva),
# classifiés par défaut selon ``Vehicule.type_fiscal`` (XFLT4) mais éditables
# (override founder). Additif, multi-société.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0033_signalementvehicule"),
    ]

    operations = [
        migrations.AddField(
            model_name="pleincarburant",
            name="tva_recuperable",
            field=models.BooleanField(
                default=True, verbose_name="TVA récupérable"
            ),
        ),
        migrations.AddField(
            model_name="pleincarburant",
            name="montant_tva",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12,
                verbose_name="Montant TVA (MAD)",
            ),
        ),
    ]
