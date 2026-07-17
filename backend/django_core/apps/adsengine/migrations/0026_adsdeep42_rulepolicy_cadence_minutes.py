"""ADSDEEP42 — RulePolicy.cadence_minutes : cadence QUART-HORAIRE opt-in.

Additif : ``cadence_minutes`` (0 = désactivé par défaut) déclenche l'évaluation
d'une règle par la boucle quart-horaire dédiée (toutes les 15 min), BORNÉE par le
budgeteur de rate-limit ADSDEEP5. Chaîne linéaire : dépend de 0025.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0025_adsdeep39_rulepolicy_name_pattern"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulepolicy",
            name="cadence_minutes",
            field=models.PositiveIntegerField(
                default=0,
                verbose_name="Cadence quart-horaire (minutes, 0 = désactivé)"),
        ),
    ]
