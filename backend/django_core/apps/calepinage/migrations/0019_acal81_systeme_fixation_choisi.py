"""ACAL81 — le système de fixation CHOISI, persisté sur le calepinage.

ADDITIVE et revertable : ``systeme_fixation`` naît à ``NULL`` pour tout
l'existant (aucun choix : la nomenclature se comporte exactement comme
avant). ``SET_NULL`` : un système retiré du catalogue laisse le calepinage
sans choix, jamais détruit.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0018_acal40_empreinte_imprimee'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='systeme_fixation',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='calepinages',
                to='calepinage.systemefixation',
                verbose_name='Système de fixation'),
        ),
    ]
