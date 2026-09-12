# VTA2 — VisiteTerrain/VisiteMedia recréés DANS L'ÉTAT d'``apps.visites`` sur
# les MÊMES tables physiques existantes (db_table='crm_visiteterrain' /
# 'crm_visitemedia') via SeparateDatabaseAndState (state-only, aucun SQL).
# Dépend de crm 0099 qui les retire de l'état crm AVANT : ainsi aucun instant
# n'a deux modèles pour la même table. Aucune donnée déplacée.
#
# La FK ``lead`` pointe 'crm.lead' par référence STRING — `apps.visites.models`
# n'importe aucun modèle de domaine (contrat `independence` d'import-linter).
# Les index sont redéclarés sous leurs noms HISTORIQUES : ils existent déjà en
# base, en changer le nom produirait du SQL.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('crm', '0099_vta2_visites_split'),
        ('records', '0013_vx210_snooze_trigger_event'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='VisiteTerrain',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('en_cours', 'En cours'), ('terminee', 'Terminée'), ('validee', 'Validée (feu vert)'), ('a_refaire', 'À refaire')], default='brouillon', max_length=12, verbose_name='Statut de la visite')),
                        ('date_prevue', models.DateField(blank=True, null=True, verbose_name='Date prévue')),
                        ('date_realisee', models.DateTimeField(blank=True, null=True, verbose_name='Date de réalisation')),
                        ('notes', models.TextField(blank=True, default='', verbose_name='Notes de visite')),
                        ('mesures', models.JSONField(blank=True, default=dict, verbose_name='Mesures relevées')),
                        ('photo_toit_key', models.CharField(blank=True, default='', max_length=500, verbose_name='Clé MinIO du toit assemblé')),
                        ('assemblage_etat', models.CharField(choices=[('aucun', 'Aucun'), ('en_cours', 'En cours'), ('ok', 'Terminé'), ('echec', 'Échec')], default='aucun', max_length=10, verbose_name="État de l'assemblage")),
                        ('assemblage_erreur', models.TextField(blank=True, default='', verbose_name="Erreur d'assemblage")),
                        ('texture_calage', models.JSONField(blank=True, null=True, verbose_name='Calage de la texture')),
                        ('commercial', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visites_terrain', to=settings.AUTH_USER_MODEL, verbose_name='Commercial terrain')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                        ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visites_terrain', to='crm.lead', verbose_name='Lead')),
                    ],
                    options={
                        'verbose_name': 'Visite technique terrain',
                        'verbose_name_plural': 'Visites techniques terrain',
                        'db_table': 'crm_visiteterrain',
                        'ordering': ['-date_prevue', '-id'],
                    },
                ),
                migrations.CreateModel(
                    name='VisiteMedia',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('slot_code', models.CharField(max_length=60, verbose_name='Slot de checklist')),
                        ('commentaire', models.TextField(blank=True, default='', verbose_name='Commentaire')),
                        ('a_refaire', models.BooleanField(default=False, verbose_name='À refaire')),
                        ('motif_refaire', models.TextField(blank=True, default='', verbose_name='Motif du renvoi')),
                        ('gps_lat', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Latitude de la prise de vue')),
                        ('gps_lng', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Longitude de la prise de vue')),
                        ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visite_medias', to='records.attachment', verbose_name='Pièce jointe')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                        ('visite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medias', to='visites.visiteterrain', verbose_name='Visite')),
                    ],
                    options={
                        'verbose_name': 'Photo de visite',
                        'verbose_name_plural': 'Photos de visite',
                        'db_table': 'crm_visitemedia',
                        'ordering': ['id'],
                    },
                ),
                migrations.AddIndex(
                    model_name='visiteterrain',
                    index=models.Index(fields=['company', 'statut'], name='crm_vterr_comp_statut_idx'),
                ),
                migrations.AddIndex(
                    model_name='visiteterrain',
                    index=models.Index(fields=['company', 'commercial'], name='crm_vterr_comp_com_idx'),
                ),
                migrations.AddIndex(
                    model_name='visitemedia',
                    index=models.Index(fields=['visite', 'slot_code'], name='crm_vmedia_visite_slot_idx'),
                ),
            ],
            database_operations=[],
        ),
    ]
