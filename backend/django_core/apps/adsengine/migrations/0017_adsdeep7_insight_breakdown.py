import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP7 — Modèle InsightBreakdown (ventilation démo/placement/région/
    horaire) + unicité par (company, cible, date, dimension, clé)."""

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('adsengine', '0016_adsdeep1_insight_columns'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsightBreakdown',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField(
                    verbose_name='ID cible')),
                ('date', models.DateField(verbose_name='Date')),
                ('dimension', models.CharField(
                    choices=[('age_gender', 'Âge × genre'),
                             ('platform', 'Placement'),
                             ('region', 'Région'), ('hourly', 'Horaire')],
                    max_length=16, verbose_name='Dimension')),
                ('key', models.CharField(
                    max_length=80, verbose_name='Clé de ventilation')),
                ('spend', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name='Dépense')),
                ('impressions', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='Impressions')),
                ('clicks', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='Clics')),
                ('results', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='Résultats')),
                ('conversations', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='Conversations')),
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
                'verbose_name': 'Ventilation de performance',
                'verbose_name_plural': 'Ventilations de performance',
                'ordering': ['-date', 'dimension', 'key'],
            },
        ),
        migrations.AddConstraint(
            model_name='insightbreakdown',
            constraint=models.UniqueConstraint(
                fields=('company', 'content_type', 'object_id', 'date',
                        'dimension', 'key'),
                name='uniq_adseng_breakdown'),
        ),
        migrations.AddIndex(
            model_name='insightbreakdown',
            index=models.Index(
                fields=['content_type', 'object_id', 'dimension'],
                name='adseng_bkdn_ct_obj_dim_idx'),
        ),
    ]
