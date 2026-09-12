"""NTDATA7 — création de `semantic.MetricDefinition` (additive, revertable)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetricDefinition',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'cle',
                    models.CharField(
                        help_text='Identifiant stable de la métrique (ex. '
                                  '« mrr », « dso ») — c\'est par cette clé '
                                  "qu'un widget, un rapport ou une alerte la "
                                  'référence.',
                        max_length=80, verbose_name='Clé'),
                ),
                ('libelle', models.CharField(max_length=150,
                                             verbose_name='Libellé')),
                (
                    'description',
                    models.TextField(
                        blank=True, default='',
                        help_text='Ce que la métrique mesure, en français '
                                  'lisible — la phrase que lira un commercial '
                                  'dans le glossaire.',
                        verbose_name='Définition'),
                ),
                (
                    'dataset',
                    models.CharField(
                        help_text="Nom d'un dataset enregistré dans "
                                  'core.data_explorer (ex. '
                                  '« ventes_factures »).',
                        max_length=80, verbose_name='Dataset'),
                ),
                (
                    'mesure',
                    models.JSONField(
                        default=dict,
                        help_text='{"field": …, "agg": …} ou {"formula": …, '
                                  '"aggregates": […]}.',
                        verbose_name='Mesure'),
                ),
                (
                    'unite',
                    models.CharField(
                        choices=[
                            ('MAD', 'Dirham (MAD)'),
                            ('%', 'Pourcentage'),
                            ('jours', 'Jours'),
                            ('nombre', 'Nombre'),
                        ],
                        default='nombre', max_length=10,
                        verbose_name='Unité'),
                ),
                (
                    'format',
                    models.PositiveSmallIntegerField(
                        default=2,
                        help_text="Décimales d'AFFICHAGE — n'altère jamais la "
                                  'valeur calculée.',
                        verbose_name='Décimales'),
                ),
                (
                    'dimensions_par_defaut',
                    models.JSONField(
                        blank=True, default=list,
                        help_text='Champs de regroupement proposés par défaut '
                                  '(ex. ["mois"]).',
                        verbose_name='Dimensions par défaut'),
                ),
                ('actif', models.BooleanField(default=True,
                                              verbose_name='Active')),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Définition de métrique',
                'verbose_name_plural': 'Définitions de métriques',
                'ordering': ['cle'],
            },
        ),
        migrations.AddConstraint(
            model_name='metricdefinition',
            constraint=models.UniqueConstraint(
                fields=('company', 'cle'),
                name='uniq_metricdefinition_company_cle'),
        ),
    ]
