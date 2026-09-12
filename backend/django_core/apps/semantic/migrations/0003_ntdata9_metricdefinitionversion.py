"""NTDATA9 — `MetricDefinitionVersion` : l'instantané immuable d'une définition.

Table NEUVE, purement additive : aucune colonne existante n'est touchée. Les
métriques déjà en base n'ont aucune version tant qu'elles n'ont pas été
enregistrées à nouveau — « aucun historique » y est la VÉRITÉ (rien n'a été
observé avant ce lot), et fabriquer une version 1 rétroactive datée
d'aujourd'hui affirmerait une date de figeage qui n'a jamais existé.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('semantic', '0002_ntdata11_filtres'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MetricDefinitionVersion',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('version', models.PositiveIntegerField(
                    default=1, verbose_name='Numéro de version')),
                ('libelle', models.CharField(
                    blank=True, default='', max_length=150,
                    verbose_name='Libellé')),
                ('dataset', models.CharField(
                    blank=True, default='', max_length=80,
                    verbose_name='Dataset')),
                ('mesure', models.JSONField(
                    blank=True, default=dict, verbose_name='Mesure')),
                ('filtres', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Filtres de la définition')),
                ('unite', models.CharField(
                    blank=True, default='', max_length=10,
                    verbose_name='Unité')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Figée le')),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'metric_definition',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='versions',
                        to='semantic.metricdefinition',
                        verbose_name='Métrique'),
                ),
                (
                    'auteur',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='metric_definition_versions',
                        to=settings.AUTH_USER_MODEL, verbose_name='Auteur'),
                ),
            ],
            options={
                'verbose_name': 'Version de définition de métrique',
                'verbose_name_plural': 'Versions de définitions de métriques',
                'ordering': ['-version', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='metricdefinitionversion',
            constraint=models.UniqueConstraint(
                fields=('company', 'metric_definition', 'version'),
                name='uniq_metricversion_co_def_version'),
        ),
    ]
