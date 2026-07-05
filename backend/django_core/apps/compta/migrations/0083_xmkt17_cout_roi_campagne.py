# XMKT17 - cout & ROI MAD par campagne : budget/cout reel + lignes de cout
# libres sur Campagne. Additif : tous les champs sont NULL/vides par defaut.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0082_xmkt14_ab_test_campagne"),
    ]

    operations = [
        migrations.AddField(
            model_name="campagne",
            name="budget_mad",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Budget prévu (MAD)"),
        ),
        migrations.AddField(
            model_name="campagne",
            name="cout_reel_mad",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Coût réel (MAD)"),
        ),
        migrations.AddField(
            model_name="campagne",
            name="lignes_cout",
            field=models.JSONField(
                blank=True, default=list,
                verbose_name="Lignes de coût (JSON)"),
        ),
    ]
