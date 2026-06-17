# D5 — logique de devis éditable (rendement, ratio de dimensionnement,
# prix cible /kWc par défaut, limite de remise). Défauts = comportement actuel.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0012_companyprofile_doc_numbering"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="rendement_global",
            field=models.DecimalField(
                decimal_places=3, default=Decimal("0.8"), max_digits=4
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="panneaux_par_900mad",
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="prix_cible_kwc_defaut",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="remise_max_pct",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True
            ),
        ),
    ]
