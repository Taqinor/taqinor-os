# AMET14 — DemandeAchat : drapeau « à revoir (V2) » + diff, additif et
# revertable (défauts False / {}).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0129_apdf40_bom_nature'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeachat',
            name='a_revoir_v2',
            field=models.BooleanField(
                default=False, verbose_name='À revoir (V2)'),
        ),
        migrations.AddField(
            model_name='demandeachat',
            name='diff_v2',
            field=models.JSONField(
                blank=True, default=dict, verbose_name='Diff V2'),
        ),
    ]
