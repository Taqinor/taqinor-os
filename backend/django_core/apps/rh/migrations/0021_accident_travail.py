# Generated 2026-06-29 — FG181 Registre HSE & accidents du travail
#
# Entièrement additive : ``CreateModel`` (``AccidentTravail``) + contrainte
# d'unicité (société, référence) + index nommés — réversible. L'accident du
# travail matérialise la DÉCLARATION HSE (date / lieu / blessé / gravité /
# arrêt / photo) et le suivi de la déclaration CNSS. Société + référence
# (race-safe, AT-YYYYMM-NNNN) posées côté serveur.
#
# RUNTIME-SAFETY (leçon FG136) : codes bornés ``gravite`` / ``statut`` ≤ 20 ;
# ``reference`` / ``lieu`` / ``photo_key`` plafonnés ; ``description`` en
# TextField (potentiellement long) ; index/contrainte nommés explicitement
# (≤ 30 chars) pour éviter la divergence d'auto-nommage Django.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('rh', '0020_emargement_epi'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccidentTravail',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('reference', models.CharField(
                    max_length=30, verbose_name='Référence')),
                ('date_accident', models.DateField(
                    verbose_name="Date de l'accident")),
                ('lieu', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Lieu')),
                ('gravite', models.CharField(
                    choices=[
                        ('leger', 'Léger'),
                        ('grave', 'Grave'),
                        ('mortel', 'Mortel'),
                    ],
                    default='leger', max_length=20,
                    verbose_name='Gravité')),
                ('description', models.TextField(
                    blank=True, default='',
                    verbose_name='Description des circonstances')),
                ('arret_travail', models.BooleanField(
                    default=False, verbose_name='Arrêt de travail')),
                ('nb_jours_arret', models.PositiveIntegerField(
                    default=0, verbose_name="Nombre de jours d'arrêt")),
                ('photo_key', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Photo (clé)')),
                ('declare_cnss', models.BooleanField(
                    default=False, verbose_name='Déclaré à la CNSS')),
                ('date_declaration_cnss', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de déclaration CNSS')),
                ('statut', models.CharField(
                    choices=[
                        ('declare', 'Déclaré'),
                        ('clos', 'Clos'),
                    ],
                    default='declare', max_length=20,
                    verbose_name='Statut')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_accidents',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_accidents',
                    to='rh.dossieremploye',
                    verbose_name='Employé blessé')),
            ],
            options={
                'verbose_name': 'Accident du travail',
                'verbose_name_plural': 'Accidents du travail',
                'ordering': ['-date_accident', '-date_creation'],
            },
        ),
        migrations.AddConstraint(
            model_name='accidenttravail',
            constraint=models.UniqueConstraint(
                fields=['company', 'reference'],
                name='rh_accident_ref_unique'),
        ),
        migrations.AddIndex(
            model_name='accidenttravail',
            index=models.Index(
                fields=['company', 'date_accident'],
                name='rh_accident_comp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='accidenttravail',
            index=models.Index(
                fields=['company', 'gravite'],
                name='rh_accident_comp_grav_idx'),
        ),
        migrations.AddIndex(
            model_name='accidenttravail',
            index=models.Index(
                fields=['company', 'statut'],
                name='rh_accident_comp_stat_idx'),
        ),
    ]
