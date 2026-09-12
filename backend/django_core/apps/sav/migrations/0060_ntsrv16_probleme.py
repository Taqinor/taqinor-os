"""NTSRV16 - Gestion Probleme (Problem Management) - purement additif.

Deux nouvelles tables, aucune colonne existante touchee :

* ``Probleme`` : le probleme de fond (titre, statut d'investigation, cause
  racine, reference PRB- race-safe via ``core.numbering``).
* ``ProblemeIncident`` : table de liaison EXPLICITE Probleme <-> Ticket
  (``related_name='incidents'``), unique par (probleme, ticket).

Resoudre un probleme ne touche JAMAIS le statut des tickets lies : ce sont
deux machines d'etats independantes - aucune donnee existante n'est modifiee
par cette migration.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('sav', '0059_ntsrv12_escalade_paliers'),
    ]

    operations = [
        migrations.CreateModel(
            name='Probleme',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                # ARC1 - socle TenantModel (created_at / updated_at).
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(
                    max_length=50, verbose_name='Référence')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('description', models.TextField(blank=True, default='')),
                ('statut', models.CharField(
                    choices=[
                        ('identifie', 'Identifié'),
                        ('en_analyse', 'En analyse'),
                        ('resolu', 'Résolu'),
                    ],
                    default='identifie', max_length=12,
                    verbose_name='Statut')),
                ('cause_racine', models.TextField(
                    blank=True, default='', verbose_name='Cause racine')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='problemes_sav',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Problème SAV',
                'verbose_name_plural': 'Problèmes SAV',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ProblemeIncident',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='problemes_incidents_sav',
                    to='authentication.company', verbose_name='Société')),
                ('probleme', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='incidents', to='sav.probleme',
                    verbose_name='Problème')),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='problemes_lies', to='sav.ticket',
                    verbose_name='Ticket')),
            ],
            options={
                'verbose_name': 'Incident rattaché à un problème',
                'verbose_name_plural': 'Incidents rattachés à un problème',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddField(
            model_name='probleme',
            name='tickets',
            field=models.ManyToManyField(
                blank=True, related_name='problemes',
                through='sav.ProblemeIncident', to='sav.ticket',
                verbose_name='Tickets liés'),
        ),
        migrations.AddIndex(
            model_name='probleme',
            index=models.Index(
                fields=['company', 'statut'],
                name='sav_probleme_statut_idx'),
        ),
        migrations.AddConstraint(
            model_name='probleme',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='sav_probleme_reference_uniq'),
        ),
        migrations.AddConstraint(
            model_name='problemeincident',
            constraint=models.UniqueConstraint(
                fields=('probleme', 'ticket'),
                name='sav_problemeincident_uniq'),
        ),
    ]
