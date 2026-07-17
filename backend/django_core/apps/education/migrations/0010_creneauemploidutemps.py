# NTEDU21 — Emploi du temps par classe (créneaux hebdomadaires récurrents).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('education', '0009_parametreseducation'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreneauEmploiDuTemps',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('jour_semaine', models.PositiveSmallIntegerField(choices=[(0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'), (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche')], verbose_name='Jour de la semaine')),
                ('heure_debut', models.TimeField(verbose_name='Heure de début')),
                ('heure_fin', models.TimeField(verbose_name='Heure de fin')),
                ('salle', models.CharField(blank=True, default='', max_length=50, verbose_name='Salle')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('classe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='creneaux_emploi_du_temps', to='education.classe', verbose_name='Classe')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('matiere_classe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='creneaux_emploi_du_temps', to='education.matiereclasse', verbose_name='Matière de classe')),
            ],
            options={
                'verbose_name': 'Créneau emploi du temps',
                'verbose_name_plural': 'Créneaux emploi du temps',
                'ordering': ['jour_semaine', 'heure_debut'],
            },
        ),
    ]
