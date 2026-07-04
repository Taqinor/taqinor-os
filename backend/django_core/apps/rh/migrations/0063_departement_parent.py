# Generated for XRH27 — hiérarchie de départements.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0062_evaluationemploye_auto_eval_issue'),
    ]

    operations = [
        migrations.AddField(
            model_name='departement',
            name='parent',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='enfants', to='rh.departement',
                verbose_name='Département parent'),
        ),
    ]
