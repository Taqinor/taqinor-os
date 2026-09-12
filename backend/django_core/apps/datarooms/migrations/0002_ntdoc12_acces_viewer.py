"""NTDOC12 — accès par viewer nommé avec expiration individuelle.

Migration ADDITIVE (nouvelle table, aucune donnée existante touchée).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.datarooms.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('datarooms', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccesSalleDonnees',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(
                    max_length=255, verbose_name='Nom du viewer')),
                ('email', models.EmailField(
                    blank=True, default='', max_length=254,
                    verbose_name='Email')),
                ('token', models.CharField(
                    default=apps.datarooms.models._default_acces_token,
                    editable=False, max_length=64, unique=True,
                    verbose_name='Jeton')),
                ('expires_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Expire le')),
                ('revoque', models.BooleanField(
                    default=False, verbose_name='Révoqué')),
                ('derniere_consultation', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Dernière consultation')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='acces_salles_donnees_crees',
                    to=settings.AUTH_USER_MODEL, verbose_name='Invité par')),
                ('salle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='acces', to='datarooms.sallededonnees',
                    verbose_name='Salle')),
            ],
            options={
                'verbose_name': 'Accès à une salle de données',
                'verbose_name_plural': 'Accès aux salles de données',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='accessalledonnees',
            index=models.Index(fields=['company', 'salle'],
                               name='dataroom_acces_co_salle_idx'),
        ),
    ]
