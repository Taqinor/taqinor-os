# XSTK3 — code-barres FABRICANT (EAN/UPC/GTIN) sur Produit. Additif,
# nullable : un produit sans code-barres garde le comportement historique
# (scan uniquement via le jeton interne `PRODUIT:<id>`). Unicité PAR SOCIÉTÉ
# quand renseigné (contrainte conditionnelle — les NULL/'' restent libres).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0053_xpur26_einvoicing_entrant"),
    ]

    operations = [
        migrations.AddField(
            model_name="produit",
            name="code_barres",
            field=models.CharField(
                blank=True, max_length=64, null=True,
                verbose_name='Code-barres fabricant (EAN/UPC/GTIN)',
                help_text='Code-barres imprimé par le fabricant (EAN-13, '
                          'UPC, GTIN…) — distinct du jeton interne de scan.'),
        ),
        migrations.AddConstraint(
            model_name="produit",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("code_barres__isnull", False),
                ) & ~models.Q(("code_barres", "")),
                fields=("company", "code_barres"),
                name="stock_produit_company_code_barres_uniq",
            ),
        ),
    ]
