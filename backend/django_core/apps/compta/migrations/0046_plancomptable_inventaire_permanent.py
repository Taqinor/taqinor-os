"""XACC6 — toggle société ``inventaire_permanent`` sur ``PlanComptable``.

Additif : nouveau champ ``default=False`` (comportement historique inchangé —
zéro écriture de stock tant que le founder n'active pas l'inventaire
permanent pour la société).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0045_modelerapprochement'),
    ]

    operations = [
        migrations.AddField(
            model_name='plancomptable',
            name='inventaire_permanent',
            field=models.BooleanField(
                default=False,
                verbose_name='Inventaire permanent (stock → GL)',
            ),
        ),
    ]
