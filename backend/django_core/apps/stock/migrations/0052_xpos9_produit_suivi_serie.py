# XPOS9 — flag additif suivi_serie sur Produit (défaut off → comportement
# inchangé). Actif : la vente comptoir capture le(s) n° de série vendu(s) et
# crée automatiquement l'équipement SAV garanti (apps.sav.services).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0051_xpur23_destination_reception"),
    ]

    operations = [
        migrations.AddField(
            model_name="produit",
            name="suivi_serie",
            field=models.BooleanField(
                default=False, verbose_name='Suivi par n° de série'),
        ),
    ]
