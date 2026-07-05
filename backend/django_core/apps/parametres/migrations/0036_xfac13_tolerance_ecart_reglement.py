# XFAC13 — Tolérance d'écart de règlement (abandon auto du résiduel).
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0035_alter_emailtemplate_cle_alter_messagetemplate_cle"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="tolerance_ecart_reglement",
            field=models.DecimalField(
                decimal_places=2, max_digits=8, default=Decimal("0"),
                help_text='Résiduel (MAD) toléré, abandonné automatiquement à '
                          "l'encaissement. 0 = désactivé (défaut)."),
        ),
    ]
