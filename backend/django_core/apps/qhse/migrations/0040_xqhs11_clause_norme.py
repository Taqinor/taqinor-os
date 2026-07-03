import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0039_xqhs10_programme_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='critereaudit',
            name='clause',
            field=models.CharField(blank=True, default='', max_length=30, verbose_name='Clause ISO'),
        ),
        migrations.AddField(
            model_name='critereaudit',
            name='referentiel',
            field=models.CharField(blank=True, choices=[('9001', 'ISO 9001'), ('14001', 'ISO 14001'), ('45001', 'ISO 45001'), ('nm', 'NM'), ('autre', 'Autre')], default='', max_length=15, verbose_name='Référentiel'),
        ),
        migrations.CreateModel(
            name='ClauseNorme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referentiel', models.CharField(choices=[('9001', 'ISO 9001'), ('14001', 'ISO 14001'), ('45001', 'ISO 45001'), ('nm', 'NM'), ('autre', 'Autre')], max_length=15, verbose_name='Référentiel')),
                ('numero', models.CharField(max_length=20, verbose_name='Numéro de clause')),
                ('intitule', models.CharField(max_length=255, verbose_name='Intitulé')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_clauses_norme', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Clause de norme',
                'verbose_name_plural': 'Clauses de norme',
                'ordering': ['referentiel', 'numero'],
            },
        ),
        migrations.AddConstraint(
            model_name='clausenorme',
            constraint=models.UniqueConstraint(fields=['company', 'referentiel', 'numero'], name='qhse_clausenorme_co_ref_num_uniq'),
        ),
    ]
