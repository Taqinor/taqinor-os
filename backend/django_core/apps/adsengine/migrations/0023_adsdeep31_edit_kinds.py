"""ADSDEEP31 — Nouveaux kinds EngineAction : surface d'édition.

EDIT_COPY / SET_SPEND_CAP / RENAME rejoignent les choix de ``kind`` (aucun
n'active/dé-pause — ils routent vers les méthodes d'édition ADSDEEP30). Dépend de
0022 (champs learning_stage_info d'AdSetMirror) : la chaîne reste strictement
linéaire.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0022_adsdeep32_adset_learning"),
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
                    ("edit_copy", "Éditer le texte / créatif"),
                    ("set_spend_cap", "Poser un plafond de dépense"),
                    ("rename", "Renommer un objet"),
                ],
                max_length=32, verbose_name="Type"),
        ),
    ]
