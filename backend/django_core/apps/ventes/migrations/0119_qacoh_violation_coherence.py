"""QA-COHERENCE — table des violations de l'auditeur de cohérence nocturne.

ADDITIVE ONLY : crée la seule table ``ventes_violationcoherence``. Aucune
table ni colonne existante n'est touchée, aucune donnée déplacée —
``git revert`` (ou ``migrate ventes 0118``) suffit à revenir en arrière.

Voir ``apps/ventes/models_coherence.py`` pour le cycle de vie
(nouvelle → vue → résolue). Multi-tenancy : ``company`` obligatoire
(TenantModel), unicité (société, empreinte).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0118_cad122_signature_domicile'),
    ]

    operations = [
        migrations.CreateModel(
            name='ViolationCoherence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule_id', models.CharField(db_index=True, max_length=64)),
                ('severity', models.CharField(max_length=20)),
                ('object_type', models.CharField(max_length=32)),
                ('object_id', models.BigIntegerField()),
                ('reference', models.CharField(blank=True, default='',
                                               max_length=80)),
                ('fingerprint', models.CharField(max_length=64)),
                ('first_seen', models.DateTimeField()),
                ('last_seen', models.DateTimeField()),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Violation de cohérence',
                'verbose_name_plural': 'Violations de cohérence',
                'db_table': 'ventes_violationcoherence',
                'ordering': ['-last_seen'],
                'indexes': [
                    models.Index(fields=['company', 'resolved_at'],
                                 name='idx_violcoh_co_resolu'),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('company', 'fingerprint'),
                        name='uniq_violationcoherence_co_empreinte'),
                ],
            },
        ),
    ]
