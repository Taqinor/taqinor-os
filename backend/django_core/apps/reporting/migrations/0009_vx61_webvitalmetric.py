import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('reporting', '0008_alter_approbationslaconfig_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebVitalMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('route', models.CharField(blank=True, default='', max_length=255)),
                ('metric', models.CharField(choices=[('LCP', 'Largest Contentful Paint'), ('INP', 'Interaction to Next Paint'), ('CLS', 'Cumulative Layout Shift'), ('TTFB', 'Time to First Byte')], max_length=10)),
                ('value', models.FloatField()),
                ('rating', models.CharField(blank=True, choices=[('good', 'Bon'), ('needs-improvement', 'À améliorer'), ('poor', 'Mauvais')], default='', max_length=20)),
                ('navigation_id', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reporting_web_vitals', to='authentication.company')),
                ('utilisateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reporting_web_vitals', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Métrique Web Vitals',
                'verbose_name_plural': 'Métriques Web Vitals',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='webvitalmetric',
            index=models.Index(fields=['company', 'route', 'metric', 'created_at'], name='rpt_vitals_p75_idx'),
        ),
    ]
