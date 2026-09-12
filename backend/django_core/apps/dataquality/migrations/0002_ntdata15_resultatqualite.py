"""NTDATA15 — journal daté des évaluations de règles (`ResultatQualite`)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('dataquality', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResultatQualite',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entite', models.CharField(max_length=80,
                                            verbose_name='Entité (dataset)')),
                ('nb_lignes', models.PositiveIntegerField(
                    default=0, verbose_name='Lignes évaluées')),
                ('nb_violations', models.PositiveIntegerField(
                    default=0, verbose_name='Violations')),
                (
                    'taux_conformite',
                    models.DecimalField(
                        blank=True, decimal_places=1, max_digits=5, null=True,
                        help_text='Vide quand la population est vide — '
                                  "« aucune donnée » n'est pas « tout est "
                                  'bon ».',
                        verbose_name='Taux de conformité (%)'),
                ),
                (
                    'echantillon',
                    models.JSONField(
                        blank=True, default=list,
                        verbose_name='Échantillon en violation'),
                ),
                ('evalue_le', models.DateTimeField(auto_now_add=True,
                                                   verbose_name='Évalué le')),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'regle',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='resultats',
                        to='dataquality.reglequalite', verbose_name='Règle'),
                ),
            ],
            options={
                'verbose_name': 'Résultat de qualité',
                'verbose_name_plural': 'Résultats de qualité',
                'ordering': ['-evalue_le', '-id'],
            },
        ),
    ]
