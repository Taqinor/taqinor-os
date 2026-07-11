# Generated for VX61 — Web Vitals réels (INP/LCP/CLS/TTFB) captés terrain.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0010_customuser_supervisor'),
        ('reporting', '0008_alter_approbationslaconfig_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='VitalMetric',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'name',
                    models.CharField(
                        choices=[
                            ('INP', 'INP'),
                            ('LCP', 'LCP'),
                            ('CLS', 'CLS'),
                            ('TTFB', 'TTFB'),
                        ],
                        max_length=10,
                    ),
                ),
                ('value', models.FloatField()),
                ('path', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'company',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='vital_metrics',
                        to='authentication.company',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Métrique Web Vital',
                'verbose_name_plural': 'Métriques Web Vitals',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='vitalmetric',
            index=models.Index(
                fields=['company', 'name', 'created_at'],
                name='reporting_v_company_e7a3d7_idx',
            ),
        ),
    ]
