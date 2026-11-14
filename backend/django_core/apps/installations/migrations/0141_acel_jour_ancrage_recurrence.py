# ACEL46 — jour d'ancrage d'une récurrence d'intervention : une récurrence du
# 31 ne glisse plus au 28 pour toujours. Additif, nullable (repli : jour de
# ``prochaine_echeance``).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0140_amsg76_intervention_rappel_j1_traite_le'),
    ]

    operations = [
        migrations.AddField(
            model_name='recurrenceintervention',
            name='jour_ancrage',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
