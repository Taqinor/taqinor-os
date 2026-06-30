# Generated for PROJ37 -- Portail d'avancement client (jeton public).

import django.db.models.deletion
from django.db import migrations, models

import apps.gestion_projet.models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0020_modeleprojet_modeletache'),
    ]

    operations = [
        migrations.CreateModel(
            name='PortailProjetToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=apps.gestion_projet.models._generer_token_portail, max_length=64, unique=True, verbose_name='Jeton')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_portail_tokens', to='authentication.company', verbose_name='Société')),
                ('projet', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='portail_token', to='gestion_projet.projet', verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Jeton de portail client',
                'verbose_name_plural': 'Jetons de portail client',
                'ordering': ['-id'],
                'indexes': [models.Index(fields=['token'], name='gp_portail_token_idx')],
            },
        ),
    ]
