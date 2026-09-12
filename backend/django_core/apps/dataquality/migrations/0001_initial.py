"""NTDATA14 — création de `dataquality.RegleQualite` (additive, revertable)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegleQualite',
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
                    'libelle',
                    models.CharField(
                        blank=True, default='',
                        help_text='Phrase lisible (ex. « ICE client au bon '
                                  'format »). Vide : un libellé est dérivé du '
                                  'type et du champ.',
                        max_length=150, verbose_name='Libellé'),
                ),
                (
                    'entite',
                    models.CharField(
                        help_text="Nom d'un dataset enregistré (ex. "
                                  '« crm_clients »).',
                        max_length=80, verbose_name='Entité (dataset)'),
                ),
                ('champ', models.CharField(max_length=120,
                                           verbose_name='Champ')),
                (
                    'type_regle',
                    models.CharField(
                        choices=[
                            ('non_vide', 'Champ renseigné'),
                            ('format', 'Format (expression régulière)'),
                            ('plage', 'Plage de valeurs'),
                            ('unicite', 'Valeur unique'),
                            ('reference_valide',
                             "Valeur d'un référentiel"),
                        ],
                        max_length=20, verbose_name='Type de règle'),
                ),
                (
                    'parametres',
                    models.JSONField(blank=True, default=dict,
                                     verbose_name='Paramètres'),
                ),
                (
                    'severite',
                    models.CharField(
                        choices=[
                            ('info', 'Information'),
                            ('avertissement', 'Avertissement'),
                            ('bloquant', 'Bloquant'),
                        ],
                        default='avertissement', max_length=15,
                        verbose_name='Sévérité'),
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
                'verbose_name': 'Règle de qualité',
                'verbose_name_plural': 'Règles de qualité',
                'ordering': ['entite', 'champ', 'id'],
            },
        ),
    ]
