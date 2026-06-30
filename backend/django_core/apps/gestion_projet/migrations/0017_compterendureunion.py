# Generated for PROJ32 -- Comptes-rendus de réunion de chantier.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_projet', '0016_actionprojet'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompteRenduReunion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chantier_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID du chantier')),
                ('titre', models.CharField(max_length=200, verbose_name='Titre')),
                ('date_reunion', models.DateField(verbose_name='Date de la réunion')),
                ('lieu', models.CharField(blank=True, default='', max_length=200, verbose_name='Lieu')),
                ('participants', models.TextField(blank=True, default='', verbose_name='Participants')),
                ('ordre_du_jour', models.TextField(blank=True, default='', verbose_name='Ordre du jour')),
                ('decisions', models.TextField(blank=True, default='', verbose_name='Décisions')),
                ('points_bloquants', models.TextField(blank=True, default='', verbose_name='Points bloquants')),
                ('date_prochaine_reunion', models.DateField(blank=True, null=True, verbose_name='Date de la prochaine réunion')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_comptes_rendus', to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comptes_rendus', to='gestion_projet.projet', verbose_name='Projet')),
                ('redacteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gestion_projet_comptes_rendus', to=settings.AUTH_USER_MODEL, verbose_name='Rédacteur')),
            ],
            options={
                'verbose_name': 'Compte-rendu de réunion',
                'verbose_name_plural': 'Comptes-rendus de réunion',
                'ordering': ['-date_reunion', '-id'],
                'indexes': [models.Index(fields=['projet', '-date_reunion'], name='gp_cr_proj_date_idx')],
            },
        ),
    ]
