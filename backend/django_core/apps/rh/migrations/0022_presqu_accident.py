# Generated 2026-06-30 — FG182 Registre des presqu'accidents (near-miss)
#
# Entièrement additive : ``CreateModel`` (``PresquAccident``) + contrainte
# d'unicité (société, référence) + index nommés — réversible. Le
# presqu'accident matérialise un événement à RISQUE qui n'a PAS causé de
# blessure (pilotage HSE proactif) : plus léger que l'accident du travail
# (FG181) — pas de blessé, pas d'arrêt, pas de déclaration CNSS. Société +
# référence (race-safe, NM-YYYYMM-NNNN) posées côté serveur ; ``declare_par``
# (l'utilisateur qui remonte) posé côté serveur.
#
# RUNTIME-SAFETY (leçon FG136) : codes bornés ``gravite_potentielle`` /
# ``statut`` ≤ 20 ; ``reference`` / ``lieu`` / ``chantier_id`` / ``photo_key``
# plafonnés ; descriptions en TextField (potentiellement longues) ;
# index/contrainte nommés explicitement (≤ 30 chars) pour éviter la divergence
# d'auto-nommage Django.

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('rh', '0021_accident_travail'),
    ]

    operations = [
        migrations.CreateModel(
            name='PresquAccident',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('reference', models.CharField(
                    max_length=30, verbose_name='Référence')),
                ('date_constat', models.DateField(
                    verbose_name='Date du constat')),
                ('lieu', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Lieu')),
                ('chantier_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='Chantier (référence)')),
                ('description', models.TextField(
                    blank=True, default='',
                    verbose_name='Description de la situation')),
                ('gravite_potentielle', models.CharField(
                    choices=[
                        ('faible', 'Faible'),
                        ('moyenne', 'Moyenne'),
                        ('elevee', 'Élevée'),
                    ],
                    default='faible', max_length=20,
                    verbose_name='Gravité potentielle')),
                ('mesure_corrective', models.TextField(
                    blank=True, default='',
                    verbose_name='Mesure corrective')),
                ('photo_key', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Photo (clé)')),
                ('statut', models.CharField(
                    choices=[
                        ('ouvert', 'Ouvert'),
                        ('traite', 'Traité'),
                    ],
                    default='ouvert', max_length=20,
                    verbose_name='Statut')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_presqu_accidents',
                    to='authentication.company',
                    verbose_name='Société')),
                ('declare_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rh_presqu_accidents_declares',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Déclaré par')),
            ],
            options={
                'verbose_name': "Presqu'accident",
                'verbose_name_plural': "Presqu'accidents",
                'ordering': ['-date_constat', '-date_creation'],
            },
        ),
        migrations.AddConstraint(
            model_name='presquaccident',
            constraint=models.UniqueConstraint(
                fields=['company', 'reference'],
                name='rh_presqaccident_ref_uniq'),
        ),
        migrations.AddIndex(
            model_name='presquaccident',
            index=models.Index(
                fields=['company', 'date_constat'],
                name='rh_presqacc_comp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='presquaccident',
            index=models.Index(
                fields=['company', 'gravite_potentielle'],
                name='rh_presqacc_comp_grav_idx'),
        ),
        migrations.AddIndex(
            model_name='presquaccident',
            index=models.Index(
                fields=['company', 'statut'],
                name='rh_presqacc_comp_stat_idx'),
        ),
    ]
