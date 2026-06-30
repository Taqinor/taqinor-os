# Generated 2026-06-30 — FG183 Causeries sécurité / toolbox talks
#
# Entièrement additive : ``CreateModel`` (``CauserieSecurite`` +
# ``CauserieParticipant``) + index nommés + contrainte d'unicité (causerie,
# participant) — réversible. La causerie sécurité matérialise le « quart d'heure
# sécurité » tenu AVANT chantier (thème / animateur / participants émargés).
# Société posée côté serveur ; chantier référencé par chaîne (pas de FK
# inter-app). RUNTIME-SAFETY (leçon FG136) : ``theme`` / ``lieu`` /
# ``chantier_id`` plafonnés, ``notes`` en TextField ; index/contrainte nommés
# explicitement (≤ 30 chars) pour éviter la divergence d'auto-nommage Django.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0022_presqu_accident'),
    ]

    operations = [
        migrations.CreateModel(
            name='CauserieSecurite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(max_length=255, verbose_name='Thème')),
                ('date_causerie', models.DateField(verbose_name='Date')),
                ('chantier_id', models.CharField(blank=True, default='', max_length=64, verbose_name='Chantier (référence)')),
                ('lieu', models.CharField(blank=True, default='', max_length=255, verbose_name='Lieu')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('animateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rh_causeries_animees', to='rh.dossieremploye', verbose_name='Animateur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_causeries_securite', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Causerie sécurité',
                'verbose_name_plural': 'Causeries sécurité',
                'ordering': ['-date_causerie', '-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='CauserieParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('present', models.BooleanField(default=True, verbose_name='Présent')),
                ('emarge', models.BooleanField(default=False, verbose_name='Émargé')),
                ('emarge_le', models.DateTimeField(blank=True, null=True, verbose_name='Émargé le')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_causerie_participants', to='authentication.company', verbose_name='Société')),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_causerie_participations', to='rh.dossieremploye', verbose_name='Participant')),
                ('causerie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participants', to='rh.causeriesecurite', verbose_name='Causerie')),
            ],
            options={
                'verbose_name': 'Participant causerie',
                'verbose_name_plural': 'Participants causerie',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='causeriesecurite',
            index=models.Index(fields=['company', 'date_causerie'], name='rh_causerie_comp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='causerieparticipant',
            index=models.Index(fields=['company', 'causerie'], name='rh_causpart_comp_caus_idx'),
        ),
        migrations.AddConstraint(
            model_name='causerieparticipant',
            constraint=models.UniqueConstraint(fields=('causerie', 'participant'), name='rh_causerie_part_unique'),
        ),
    ]
