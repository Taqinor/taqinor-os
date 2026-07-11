# VX96 — Lead devient le premier adoptant du soft-delete partagé
# (core.SoftDeleteModel, FG388). Migration ADDITIVE : trois champs nullables
# (is_deleted / deleted_at / deleted_by) + bascule des managers vers le manager
# « vivants uniquement » (objects) + all_objects. Aucune ligne existante n'est
# supprimée ; toutes restent is_deleted=False (défaut).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import core.models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0053_qx35_client_code_parrainage"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="is_deleted",
            field=models.BooleanField(
                db_index=True, default=False, verbose_name="Supprimé"
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Supprimé le"
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Supprimé par",
            ),
        ),
        migrations.AlterModelManagers(
            name="lead",
            managers=[
                ("objects", core.models.SoftDeleteManager()),
                ("all_objects", models.Manager()),
            ],
        ),
    ]
