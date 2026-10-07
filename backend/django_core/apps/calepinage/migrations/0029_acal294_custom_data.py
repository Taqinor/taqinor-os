# ACAL294 (D-ACAL-20) — Calepinage.custom_data : les champs personnalisés de
# la société (patron crm.Lead). Colonne additive nullable : aucune réécriture
# de table, documents existants à null. Réversible (RemoveField).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0028_acal267_pose_reelle_zone_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='custom_data',
            field=models.JSONField(blank=True, null=True,
                                   verbose_name='Champs personnalisés'),
        ),
    ]
