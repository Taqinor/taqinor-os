"""CALX358 — le catalogue de systèmes de fixation : ``SystemeFixation`` et
``ComposantFixation``.

ADDITIVE et SANS DONNÉE : les deux tables naissent VIDES. Un catalogue vide
veut dire « aucune nomenclature de fixation n'est calculée » — exactement le
comportement d'aujourd'hui (D12). ``produit_id`` est un identifiant OPAQUE
(aucune FK dure vers le stock, aucune dépendance de migration ajoutée).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('calepinage', '0013_calx347_approbation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemeFixation',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.SlugField(max_length=60,
                                          verbose_name='Code')),
                ('libelle', models.CharField(max_length=200,
                                             verbose_name='Libellé')),
                ('fabricant', models.CharField(blank=True, default='',
                                               max_length=120,
                                               verbose_name='Fabricant')),
                ('mode_pose', models.CharField(
                    choices=[('toiture_inclinee', 'Toiture inclinée'),
                             ('toit_plat_leste', 'Toit plat — lesté'),
                             ('toit_plat_fixe', 'Toit plat — fixé'),
                             ('sol', 'Au sol'),
                             ('ombriere', 'Ombrière'),
                             ('autre', 'Autre')],
                    default='toiture_inclinee', max_length=20,
                    verbose_name='Mode de pose')),
                ('actif', models.BooleanField(default=True,
                                              verbose_name='Actif')),
                ('provenance', models.TextField(verbose_name='Provenance')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Système de fixation',
                'verbose_name_plural': 'Systèmes de fixation',
                'ordering': ['libelle', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ComposantFixation',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('produit_id', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name='Produit (identifiant)')),
                ('role', models.CharField(
                    choices=[('rail', 'Rail'),
                             ('pince_milieu', 'Pince de milieu'),
                             ('pince_fin', 'Pince de fin'),
                             ('crochet', 'Crochet'),
                             ('embout', 'Embout'),
                             ('lest', 'Lest'),
                             ('visserie', 'Visserie')],
                    max_length=20, verbose_name='Rôle')),
                ('libelle', models.CharField(max_length=160,
                                             verbose_name='Composant')),
                ('unite', models.CharField(max_length=12,
                                           verbose_name='Unité')),
                ('regle', models.JSONField(blank=True, default=dict,
                                           verbose_name='Règle de quantité')),
                ('source', models.TextField(verbose_name='Source')),
                ('ordre', models.PositiveIntegerField(default=0,
                                                      verbose_name='Ordre')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('systeme', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='composants',
                    to='calepinage.systemefixation',
                    verbose_name='Système de fixation')),
            ],
            options={
                'verbose_name': 'Composant de fixation',
                'verbose_name_plural': 'Composants de fixation',
                'ordering': ['systeme', 'ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='systemefixation',
            index=models.Index(fields=['company', 'actif'],
                               name='cal_sfx_co_actif_idx'),
        ),
        migrations.AddConstraint(
            model_name='systemefixation',
            constraint=models.UniqueConstraint(
                fields=('company', 'code'),
                name='uniq_systeme_fixation_code_par_societe'),
        ),
        migrations.AddIndex(
            model_name='composantfixation',
            index=models.Index(fields=['company', 'systeme'],
                               name='cal_cfx_co_sys_idx'),
        ),
    ]
