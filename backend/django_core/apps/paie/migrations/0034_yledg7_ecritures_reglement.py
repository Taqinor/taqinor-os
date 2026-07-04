# Generated manually — YLEDG7 écritures de règlement (OV salaires +
# organismes sociaux) : champs additifs d'idempotence, aucune donnée
# existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):
    """YLEDG7 — OrdreVirement/EcheanceDeclarative.ecriture_reglement_id (additif)."""

    dependencies = [
        ("paie", "0033_xpai21_bulletin_lu_le"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordrevirement",
            name="ecriture_reglement_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Écriture de règlement (compta)"),
        ),
        migrations.AddField(
            model_name="ordrevirement",
            name="date_reglement",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Réglé le"),
        ),
        migrations.AddField(
            model_name="echeancedeclarative",
            name="ecriture_reglement_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Écriture de règlement (compta)"),
        ),
    ]
