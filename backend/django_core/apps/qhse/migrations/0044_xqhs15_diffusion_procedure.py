import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0043_xqhs14_risque_opportunite'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DiffusionProcedure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('population_cible', models.JSONField(blank=True, default=dict, verbose_name='Population cible')),
                ('date_diffusion', models.DateTimeField(auto_now_add=True, verbose_name='Diffusée le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_diffusions_procedure', to='authentication.company', verbose_name='Société')),
                ('procedure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diffusions', to='qhse.procedurequalite', verbose_name='Procédure (version)')),
            ],
            options={
                'verbose_name': 'Diffusion de procédure',
                'verbose_name_plural': 'Diffusions de procédure',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='AccuseLecture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lu_le', models.DateTimeField(blank=True, null=True, verbose_name='Lu le (signature serveur)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_accuses_lecture', to='authentication.company', verbose_name='Société')),
                ('diffusion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accuses_lecture', to='qhse.diffusionprocedure', verbose_name='Diffusion')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_accuses_lecture', to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur')),
            ],
            options={
                'verbose_name': 'Accusé de lecture',
                'verbose_name_plural': 'Accusés de lecture',
                'ordering': ['-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='accuselecture',
            constraint=models.UniqueConstraint(fields=['diffusion', 'user'], name='qhse_accuselecture_diffusion_user_uniq'),
        ),
    ]
