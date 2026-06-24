# Generated for FG52 — Multi-currency quoting/invoicing.
# Adds devise_defaut (default MAD) to CompanyProfile.
# Additive, reversible: no existing row is modified.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0024_emailtemplate"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="devise_defaut",
            field=models.CharField(
                default="MAD",
                help_text=(
                    "Code ISO 4217 appliqué par défaut aux nouveaux devis/factures "
                    "(ex. MAD, EUR, USD). Défaut MAD."
                ),
                max_length=10,
                verbose_name="Devise par défaut",
            ),
        ),
    ]
