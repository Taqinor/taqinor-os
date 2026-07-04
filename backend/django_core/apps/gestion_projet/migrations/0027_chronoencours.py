# Generated for XPRJ5 -- Task start/stop timer (chrono).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0026_situationtravaux_lignesituation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChronoEnCours',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('demarre_a', models.DateTimeField(verbose_name='Démarré à')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gestion_projet_chronos',
                    to='authentication.company', verbose_name='Société')),
                ('tache', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chronos', to='gestion_projet.tache',
                    verbose_name='Tâche')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gestion_projet_chrono_actif',
                    to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur')),
            ],
            options={
                'verbose_name': 'Chrono en cours',
                'verbose_name_plural': 'Chronos en cours',
                'ordering': ['-demarre_a'],
            },
        ),
    ]
