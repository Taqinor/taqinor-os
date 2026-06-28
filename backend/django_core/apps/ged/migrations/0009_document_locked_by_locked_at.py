# GED16 — Check-out / check-in (verrouillage optimiste).
#
# Ajoute deux champs nullable sur Document :
#   - `locked_by`  FK nullable vers settings.AUTH_USER_MODEL
#   - `locked_at`  DateTimeField nullable
# Additive et réversible.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ged", "0008_documentversion_restored_from"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="locked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ged_documents_verrou",
                to=settings.AUTH_USER_MODEL,
                verbose_name="verrouille par",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="locked_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="verrouille le",
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["locked_by"],
                name="ged_doc_locked_by_idx",
            ),
        ),
    ]
