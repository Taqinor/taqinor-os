# NTRET25 — Arrondi caisse (cash rounding, espèces uniquement) configurable
# dans Paramètres POS (onglet Point de vente). Additif — désactivé par
# défaut, comportement historique inchangé (aucun arrondi appliqué).
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0072_ntret23_delai_expiration_click_collect"),
    ]

    operations = [
        migrations.AddField(
            model_name="parametrespos",
            name="arrondi_caisse_actif",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="parametrespos",
            name="arrondi_caisse_pas",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.05"), max_digits=4,
                help_text="Pas d'arrondi caisse en espèces (MAD), ex. 0.05 ou 0.10."),
        ),
    ]
