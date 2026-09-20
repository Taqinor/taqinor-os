"""PUB128 — Harnais des tests terrain : modèle ``FieldTestResult``.

Les 7 inconnues terrain (ADSENG37) vivaient en CONSTANTES et la porte de
préflight ``field_tests_complete`` ne pouvait basculer que par un edit de code.
Ce modèle porte le résultat MESURÉ d'un micro-test (valeur, preuve, date) par
société : ``field_tests.pending_keys`` lit désormais la DB d'abord, les
constantes restant le repli.

Purement ADDITIVE (une nouvelle table, aucune colonne existante touchée),
entièrement revertable. Unicité par ``(company, ft)`` : ré-enregistrer met à
jour le résultat au lieu de créer un second verdict concurrent.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('adsengine', '0055_pub126_creative_asset_ai_generated'),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldTestResult',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ft', models.CharField(
                    choices=[
                        ('FT1', "FT1 — seuils de reset d'apprentissage"),
                        ('FT2', "FT2 — budget minimum d'un split-test"),
                        ('FT3', 'FT3 — défauts des enhancements Advantage+'),
                        ('FT4', 'FT4 — granularité du reporting DCO'),
                        ('FT5', 'FT5 — coûts BUC lecture / écriture'),
                        ('FT6', 'FT6 — rotation intra-ad-set réglable par API'),
                        ('FT7', "FT7 — gating par palier d'accès"),
                    ],
                    max_length=8, verbose_name='Micro-test')),
                ('measured_value', models.CharField(
                    max_length=255, verbose_name='Valeur mesurée')),
                ('evidence', models.TextField(
                    blank=True, default='',
                    verbose_name=('Preuve (capture, ID de campagne, extrait '
                                  'de réponse)'))),
                ('measured_on', models.DateField(verbose_name='Mesuré le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('recorded_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='adsengine_field_test_results',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Enregistré par')),
            ],
            options={
                'verbose_name': 'Résultat de test terrain',
                'verbose_name_plural': 'Résultats de tests terrain',
                'ordering': ['ft'],
            },
        ),
        migrations.AddConstraint(
            model_name='fieldtestresult',
            constraint=models.UniqueConstraint(
                fields=('company', 'ft'), name='uniq_adseng_field_test'),
        ),
        migrations.AddIndex(
            model_name='fieldtestresult',
            index=models.Index(fields=['company', 'ft'],
                               name='adseng_fieldtest_co_ft_idx'),
        ),
    ]
