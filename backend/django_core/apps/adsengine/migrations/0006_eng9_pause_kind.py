from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0005_eng8_capability_toggles"),
    ]

    operations = [
        migrations.AlterField(
            model_name="engineaction",
            name="kind",
            field=models.CharField(
                choices=[
                    ("create_campaign", "Créer une campagne"),
                    ("create_adset", "Créer un ad set"),
                    ("create_ad", "Créer une ad"),
                    ("rotate_creative", "Roter le créatif"),
                    ("rebalance_budget", "Rééquilibrer le budget"),
                    ("pause", "Mettre en pause"),
                ],
                max_length=32, verbose_name="Type"),
        ),
    ]
