"""ADSDEEP39 — RulePolicy : motif de sélection dynamique par nom (Selection Filter).

Additif : ``name_pattern`` (glob insensible à la casse) restreint DYNAMIQUEMENT
la règle aux objets dont le nom matche — y compris les campagnes créées APRÈS la
règle (le moteur relit les miroirs à chaque beat). Vide = toute la société.
Chaîne linéaire : dépend de 0024.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0024_adsdeep34_experiment_study_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulepolicy",
            name="name_pattern",
            field=models.CharField(
                blank=True, default="", max_length=120,
                verbose_name="Motif de nom (sélection dynamique)"),
        ),
    ]
