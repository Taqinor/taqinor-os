import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0035_xqhs6_scar'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyseNcr',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cinq_pourquoi', models.JSONField(blank=True, default=list, verbose_name='5-Pourquoi')),
                ('huit_d', models.JSONField(blank=True, default=dict, verbose_name='8D')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_analyses_ncr', to='authentication.company', verbose_name='Société')),
                ('non_conformite', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analyse', to='qhse.nonconformite', verbose_name='Non-conformité')),
            ],
            options={
                'verbose_name': 'Analyse NCR (5-Pourquoi / 8D)',
                'verbose_name_plural': 'Analyses NCR (5-Pourquoi / 8D)',
                'ordering': ['-id'],
            },
        ),
    ]
