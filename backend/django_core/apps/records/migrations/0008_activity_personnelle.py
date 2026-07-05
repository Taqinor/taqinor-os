# XKB4 — à-faire personnel : Activity.content_type/object_id deviennent
# nullable (un à-faire personnel n'a pas de cible métier) + champ additif
# `personnelle` (défaut False, rétro-compatible : toute activité existante a
# déjà une cible et reste non-personnelle). Entièrement additive et
# réversible (`migrate records 0007`).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("records", "0007_comment_resolved"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="personnelle",
            field=models.BooleanField(
                default=False, verbose_name="À-faire personnel"),
        ),
        migrations.AlterField(
            model_name="activity",
            name="content_type",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="contenttypes.contenttype"),
        ),
        migrations.AlterField(
            model_name="activity",
            name="object_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
