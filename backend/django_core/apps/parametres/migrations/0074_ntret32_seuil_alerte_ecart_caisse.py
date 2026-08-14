# NTRET32 — Alerte fondateur/gérant sur écart de caisse anormal : seuil
# configurable dans Paramètres POS (onglet Point de vente). Additif —
# NULL/0 = désactivé, comportement historique inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0073_ntret25_arrondi_caisse"),
    ]

    operations = [
        migrations.AddField(
            model_name="parametrespos",
            name="seuil_alerte_ecart_caisse",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text="Seuil (MAD, écart absolu) déclenchant une alerte "
                          "de clôture anormale. Vide/0 = désactivé."),
        ),
    ]
