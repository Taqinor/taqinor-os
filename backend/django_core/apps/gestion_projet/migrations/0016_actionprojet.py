# Generated for PROJ31 -- Registre d'actions.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_projet', '0015_risque'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActionProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('statut', models.CharField(choices=[('a_faire', 'À faire'), ('en_cours', 'En cours'), ('fait', 'Fait'), ('annule', 'Annulé')], default='a_faire', max_length=10, verbose_name='Statut')),
                ('priorite', models.CharField(choices=[('basse', 'Basse'), ('moyenne', 'Moyenne'), ('haute', 'Haute')], default='moyenne', max_length=10, verbose_name='Priorité')),
                ('echeance', models.DateField(blank=True, null=True, verbose_name='Échéance')),
                ('date_cloture', models.DateField(blank=True, null=True, verbose_name='Date de clôture')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_actions', to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='gestion_projet.projet', verbose_name='Projet')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gestion_projet_actions', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
                ('risque', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='actions', to='gestion_projet.risque', verbose_name='Risque lié')),
            ],
            options={
                'verbose_name': 'Action projet',
                'verbose_name_plural': 'Actions projet',
                'ordering': ['statut', 'echeance', '-id'],
                'indexes': [models.Index(fields=['projet', 'statut'], name='gp_action_proj_stat_idx')],
            },
        ),
    ]
