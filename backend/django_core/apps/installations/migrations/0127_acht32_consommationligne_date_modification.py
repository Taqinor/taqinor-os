# ACHT32 — date de dernière modification en ligne d'une ligne de consommation
# (base de la détection de conflit des ops terrain). Additive, revertable.

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0126_acht19_notifie_livree_le'),
    ]

    operations = [
        migrations.AddField(
            model_name='consommationligne',
            name='date_modification',
            field=models.DateTimeField(
                auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
