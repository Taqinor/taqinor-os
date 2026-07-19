# PUB104 — Rollup/archivage mensuel des InsightSnapshot : modèle
# InsightMonthlyRollup (agrégats additifs par objet × mois) + unicité par
# (company, cible, année, mois). Additif.
#
# NOTE ORCHESTRATEUR : chaîné après 0103 (PUB103) dans cette worktree ancrée à
# 0033 — re-chaîner sur la vraie dernière migration au fold.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('adsengine', '0103_pub103_four_eyes'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsightMonthlyRollup',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField(
                    verbose_name='ID cible')),
                ('year', models.PositiveIntegerField(verbose_name='Année')),
                ('month', models.PositiveIntegerField(verbose_name='Mois')),
                ('spend', models.DecimalField(
                    decimal_places=2, default=0, max_digits=16,
                    verbose_name='Dépense')),
                ('results', models.PositiveIntegerField(
                    default=0, verbose_name='Résultats')),
                ('impressions', models.PositiveIntegerField(
                    default=0, verbose_name='Impressions')),
                ('clicks', models.PositiveIntegerField(
                    default=0, verbose_name='Clics')),
                ('link_clicks', models.PositiveIntegerField(
                    default=0, verbose_name='Clics sur lien')),
                ('conversations', models.PositiveIntegerField(
                    default=0, verbose_name='Conversations')),
                ('leads_count', models.PositiveIntegerField(
                    default=0, verbose_name='Leads')),
                ('days_count', models.PositiveIntegerField(
                    default=0, verbose_name='Jours agrégés')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype',
                    verbose_name='Type de cible')),
            ],
            options={
                'verbose_name': 'Rollup mensuel de performance',
                'verbose_name_plural': 'Rollups mensuels de performance',
                'ordering': ['-year', '-month'],
            },
        ),
        migrations.AddConstraint(
            model_name='insightmonthlyrollup',
            constraint=models.UniqueConstraint(
                fields=('company', 'content_type', 'object_id', 'year', 'month'),
                name='uniq_adseng_insight_rollup'),
        ),
        migrations.AddIndex(
            model_name='insightmonthlyrollup',
            index=models.Index(
                fields=['company', 'year', 'month'],
                name='adseng_rollup_co_ym_idx'),
        ),
    ]
