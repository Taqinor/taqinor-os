"""ARC1 — PhotoChecklistMeta (NTMOB11) bascule sur core.models.TenantModel
(SCA4 : plus de FK company hors-socle) : ajoute les timestamps standard
created_at/updated_at hérités de TimestampedModel. `company` elle-même est
INCHANGÉE (nullable, comme posée par 0098) — aucune AlterField, purement
additif."""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0099_ntmob16_installation_signature_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='photochecklistmeta',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='photochecklistmeta',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
