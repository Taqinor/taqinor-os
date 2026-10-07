"""AANA32 — ``ApiEvent.payload`` encodé par ``DjangoJSONEncoder``.

Migration d'ÉTAT (aucune opération SQL : l'encodeur n'existe que côté Python),
revertable.
"""
import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0019_ntapi38_apicalllog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='apievent',
            name='payload',
            field=models.JSONField(
                blank=True, default=dict,
                encoder=django.core.serializers.json.DjangoJSONEncoder),
        ),
    ]
