# Generated manually — GED15 versioning + restore audit trail.
#
# Adds a nullable self-FK `restored_from` on DocumentVersion: when a restore
# action creates a new version by cloning a prior one, this field points to the
# source version for full auditability.  Additive and revertable.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ged", "0007_document_embedding"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentversion",
            name="restored_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ged_restorations",
                to="ged.documentversion",
                verbose_name="restaurée depuis",
            ),
        ),
    ]
