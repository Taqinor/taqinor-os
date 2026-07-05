# XFAC24 — Immutabilité de la facture émise (opt-in) — correction par avoir
# uniquement.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0037_xfac18_revue_factures_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="factures_immuables",
            field=models.BooleanField(
                default=False,
                help_text="Interdit la modification des champs financiers "
                          "d'une facture non-brouillon (correction par "
                          "avoir uniquement)."),
        ),
    ]
