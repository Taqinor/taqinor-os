# Journal des écrasements d'import : garde-fou « remplissage seul » + valeurs
# précédentes conservées par ligne. Purement ADDITIF et réversible (aucune
# colonne supprimée/renommée, chaque ajout a un défaut).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataimport',
         '0003_rename_dataimport__content_45a3e1_idx_dataimport__content_15caa2_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='importjob',
            name='ecraser',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='importjob',
            name='ecrasement_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='importjob',
            name='refus_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='importjobrow',
            name='cible_type',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='importjobrow',
            name='cible_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='importjobrow',
            name='modifications',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='importjobrow',
            name='refuses',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
