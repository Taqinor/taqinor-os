import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0048_xqhs19_incident_environnement'),
    ]

    operations = [
        migrations.CreateModel(
            name='AspectEnvironnemental',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activite', models.CharField(max_length=255, verbose_name='Activité')),
                ('aspect', models.CharField(max_length=255, verbose_name='Aspect')),
                ('impact', models.CharField(max_length=255, verbose_name='Impact')),
                ('condition', models.CharField(choices=[('normale', 'Normale'), ('anormale', 'Anormale'), ('urgence', 'Urgence')], default='normale', max_length=10, verbose_name='Condition')),
                ('frequence', models.PositiveSmallIntegerField(default=1, verbose_name='Fréquence (1-5)')),
                ('gravite', models.PositiveSmallIntegerField(default=1, verbose_name='Gravité (1-5)')),
                ('seuil_significativite', models.PositiveIntegerField(default=12, verbose_name='Seuil de significativité')),
                ('controles_existants', models.TextField(blank=True, default='', verbose_name='Contrôles opérationnels existants')),
                ('date_revue', models.DateField(blank=True, null=True, verbose_name='Date de revue')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_aspects_environnementaux', to='authentication.company', verbose_name='Société')),
                ('procedure', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aspects_environnementaux', to='qhse.procedurequalite', verbose_name='Procédure liée')),
                ('objectif', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aspects_environnementaux', to='qhse.objectifqhse', verbose_name='Objectif QHSE lié')),
            ],
            options={
                'verbose_name': 'Aspect environnemental',
                'verbose_name_plural': 'Aspects environnementaux',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='aspectenvironnemental',
            index=models.Index(fields=['company', 'condition'], name='qhse_aspenv_co_cond'),
        ),
    ]
