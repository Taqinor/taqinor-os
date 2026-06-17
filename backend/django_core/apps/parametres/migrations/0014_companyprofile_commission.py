# N99 — commission commerciale (mode + valeur). Additif, désactivé par défaut
# (mode 'off') : aucun comportement existant n'est modifié.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0013_companyprofile_quote_logic"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="commission_mode",
            field=models.CharField(default="off", max_length=10),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="commission_valeur",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
    ]
