# Generated for XFLT11 — Imputation automatique du conducteur sur les
# infractions. Ajoute des champs additifs sur ``Infraction`` (imputation_auto,
# date_limite_contestation, refacture_conducteur, montant_retenu). Additif,
# multi-société.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0035_parametreamortissementcgi"),
    ]

    operations = [
        migrations.AddField(
            model_name="infraction",
            name="imputation_auto",
            field=models.BooleanField(
                default=False, verbose_name="Conducteur imputé automatiquement"
            ),
        ),
        migrations.AddField(
            model_name="infraction",
            name="date_limite_contestation",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date limite de contestation",
            ),
        ),
        migrations.AddField(
            model_name="infraction",
            name="refacture_conducteur",
            field=models.BooleanField(
                default=False, verbose_name="Refacturée au conducteur"
            ),
        ),
        migrations.AddField(
            model_name="infraction",
            name="montant_retenu",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Montant retenu (MAD)",
            ),
        ),
    ]
