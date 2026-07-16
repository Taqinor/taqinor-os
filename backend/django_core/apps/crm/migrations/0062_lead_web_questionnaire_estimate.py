# Quote-journey — Lead: questionnaire web (pro/agricole) sans colonne
# d'accueil + estimation montrée au visiteur (snapshot whitelisté).
# Purement additif, réversible via le reverse automatique d'AddField.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0061_adseng1_lead_meta_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="web_questionnaire",
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name="Questionnaire web (quote-journey)",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="web_estimate",
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name="Estimation montrée (web)",
            ),
        ),
    ]
