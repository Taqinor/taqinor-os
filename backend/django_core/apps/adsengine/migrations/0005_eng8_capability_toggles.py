from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0004_engineaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="guardrailconfig",
            name="auto_rotate_creative",
            field=models.BooleanField(
                default=False,
                verbose_name="Auto — rotation créative (ENG8)"),
        ),
        migrations.AddField(
            model_name="guardrailconfig",
            name="auto_rebalance_within_band",
            field=models.BooleanField(
                default=False,
                verbose_name="Auto — rééquilibrage dans la bande (ENG8)"),
        ),
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
                ],
                max_length=32, verbose_name="Type"),
        ),
    ]
