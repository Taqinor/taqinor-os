# N43 — seuils éditables du régime loi 82-21 (kWc).

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0010_settingsauditlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="seuil_regime_declaration_kwc",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("11"), max_digits=8
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="seuil_regime_anre_kwc",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("1000"), max_digits=10
            ),
        ),
    ]
