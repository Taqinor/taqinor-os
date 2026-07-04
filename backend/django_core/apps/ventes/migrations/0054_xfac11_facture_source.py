# XFAC11 — Facture consolidée multi-devis/BC d'un même client : table de
# liaison FactureSource (traçabilité), Facture.devis reste inchangé (nullable).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0053_xfac10_proforma"),
    ]

    operations = [
        migrations.AddField(
            model_name="lignefacture",
            name="source_devis",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lignes_facture_consolidee", to="ventes.devis"),
        ),
        migrations.CreateModel(
            name="FactureSource",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name="ID")),
                ("sous_total_ht", models.DecimalField(decimal_places=2, max_digits=12)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="facture_sources", to="authentication.company")),
                ("devis", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="factures_sources", to="ventes.devis")),
                ("facture", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sources", to="ventes.facture")),
            ],
            options={
                "verbose_name": "Source de facture consolidée",
                "verbose_name_plural": "Sources de facture consolidée",
                "unique_together": {("facture", "devis")},
            },
        ),
    ]
