# Generated 2026-06-30 — FG188 Plan & registre de formation (besoins)
#
# Entièrement additive : ``CreateModel`` (``BesoinFormation``) + index nommés —
# réversible. Le besoin de formation porte un thème, une priorité, une échéance
# optionnelle, un drapeau d'obligation réglementaire (OFPPT / CSF) et un statut
# (identifié → planifié → satisfait). Il peut être rattaché à une session de
# formation (FK même app ``rh.SessionFormation``) qui le couvre. Le REGISTRE par
# employé (historique réalisé) est un SÉLECTEUR sur ``InscriptionFormation`` —
# pas de table dédiée. Société posée côté serveur. RUNTIME-SAFETY (leçon FG136) :
# codes bornés ``priorite`` / ``statut`` / ``type_obligation`` ≤ 20 ; ``theme``
# plafonné ; ``notes`` en TextField ; index nommés explicitement (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0025_session_formation'),
    ]

    operations = [
        migrations.CreateModel(
            name='BesoinFormation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(max_length=200, verbose_name='Thème')),
                ('priorite', models.CharField(choices=[('basse', 'Basse'), ('moyenne', 'Moyenne'), ('haute', 'Haute')], default='moyenne', max_length=20, verbose_name='Priorité')),
                ('echeance', models.DateField(blank=True, null=True, verbose_name='Échéance souhaitée')),
                ('obligation_reglementaire', models.BooleanField(default=False, verbose_name='Obligation réglementaire')),
                ('type_obligation', models.CharField(blank=True, choices=[('ofppt', 'OFPPT'), ('csf', 'CSF (Contrats Spéciaux de Formation)'), ('autre', 'Autre')], default='', max_length=20, verbose_name="Type d'obligation")),
                ('statut', models.CharField(choices=[('identifie', 'Identifié'), ('planifie', 'Planifié'), ('satisfait', 'Satisfait')], default='identifie', max_length=20, verbose_name='Statut')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_besoins_formation', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='besoins_formation', to='rh.dossieremploye', verbose_name='Employé')),
                ('session_liee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='besoins_couverts', to='rh.sessionformation', verbose_name='Session liée')),
            ],
            options={
                'verbose_name': 'Besoin de formation',
                'verbose_name_plural': 'Besoins de formation',
                'ordering': ['-priorite', 'echeance', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='besoinformation',
            index=models.Index(fields=['company', 'statut'], name='rh_bf_comp_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='besoinformation',
            index=models.Index(fields=['company', 'employe'], name='rh_bf_comp_emp_idx'),
        ),
    ]
