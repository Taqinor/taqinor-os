# Generated for PROJ17 -- Indisponibilités ressources.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0011_affectationressource'),
    ]

    operations = [
        migrations.CreateModel(
            name='Indisponibilite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_indispo', models.CharField(choices=[('conge', 'Congé'), ('formation', 'Formation'), ('arret', 'Arrêt')], default='conge', max_length=20, verbose_name="Type d'indisponibilité")),
                ('date_debut', models.DateField(verbose_name='Date de début')),
                ('date_fin', models.DateField(verbose_name='Date de fin')),
                ('motif', models.TextField(blank=True, default='', verbose_name='Motif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gp_indisponibilites', to='authentication.company', verbose_name='Société')),
                ('ressource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gp_indisponibilites', to='gestion_projet.ressourceprofil', verbose_name='Ressource (profil)')),
            ],
            options={
                'verbose_name': 'Indisponibilité ressource',
                'verbose_name_plural': 'Indisponibilités ressources',
                'ordering': ['ressource', 'date_debut', 'id'],
                'indexes': [models.Index(fields=['ressource', 'date_debut'], name='gp_indispo_res_debut_idx'), models.Index(fields=['company', 'date_debut'], name='gp_indispo_co_debut_idx')],
            },
        ),
    ]
