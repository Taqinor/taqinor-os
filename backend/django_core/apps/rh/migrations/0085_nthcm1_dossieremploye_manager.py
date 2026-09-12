# NTHCM1 — ligne hiérarchique réelle sur le dossier employé.
#
# ADDITIF et sans défaut inventé : `manager=NULL` partout au backfill (un
# `null=True` sans `default` ne réécrit aucune ligne existante).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0084_aud718_justificatif_cv_minio'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossieremploye',
            name='manager',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='subordonnes',
                to='rh.dossieremploye',
                verbose_name='Manager (hiérarchique)'),
        ),
    ]
