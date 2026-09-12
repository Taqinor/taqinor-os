"""NTDATA23 — `RegleSurvivorship` : qui gagne, champ par champ, à la fusion.

Table NEUVE, purement additive. Aucune règle n'existe au départ : la
consolidation applique alors la stratégie PAR DÉFAUT déclarée dans
``dataquality.services`` et l'inscrit dans le golden record — le comportement
est donc explicite dès la première exécution, sans paramétrage préalable.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('dataquality', '0003_ntdata22_goldenrecord'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegleSurvivorship',
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
                    'entite',
                    models.CharField(
                        choices=[('client', 'Client'),
                                 ('fournisseur', 'Fournisseur'),
                                 ('produit', 'Produit')],
                        max_length=20, verbose_name='Entité'),
                ),
                ('champ', models.CharField(max_length=120,
                                           verbose_name='Champ')),
                (
                    'strategie',
                    models.CharField(
                        choices=[
                            ('plus_recent',
                             'La fiche la plus récemment modifiée'),
                            ('plus_complet', 'La fiche la plus renseignée'),
                            ('source_prioritaire', 'La fiche prioritaire'),
                            ('plus_frequent', 'La valeur la plus fréquente'),
                        ],
                        default='source_prioritaire', max_length=25,
                        verbose_name='Stratégie'),
                ),
                (
                    'parametres',
                    models.JSONField(
                        blank=True, default=dict, verbose_name='Paramètres',
                        help_text='{"source_id": <id>} pour « fiche '
                                  'prioritaire ».'),
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
                'verbose_name': 'Règle de survivorship',
                'verbose_name_plural': 'Règles de survivorship',
                'ordering': ['entite', 'champ', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='reglesurvivorship',
            constraint=models.UniqueConstraint(
                fields=('company', 'entite', 'champ'),
                name='uniq_survivorship_co_entite_champ'),
        ),
    ]
