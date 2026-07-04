# Generated manually — ZRH2 garde d'idempotence de l'acquisition mensuelle
# automatique (accruer_conges) + report janvier. Additif.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH2 — SoldeConge.mois_acquis + report_applique (additif)."""

    dependencies = [
        ("rh", "0070_yhire14_approbation_ouverture"),
    ]

    operations = [
        migrations.AddField(
            model_name="soldeconge",
            name="mois_acquis",
            field=models.PositiveSmallIntegerField(
                default=0,
                verbose_name="Mois déjà crédités (acquisition auto)"),
        ),
        migrations.AddField(
            model_name="soldeconge",
            name="report_applique",
            field=models.BooleanField(
                default=False, verbose_name="Report N-1 déjà appliqué"),
        ),
    ]
