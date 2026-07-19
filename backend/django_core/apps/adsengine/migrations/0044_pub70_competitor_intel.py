# PUB70 — Veille concurrentielle (périmètre honnête, ZÉRO scraping — règle #5) :
# CompetitorPage (Page suivie + lien Ad Library web profond) +
# CompetitorAdObservation (hooks/angles SAISIS manuellement, jamais collectés).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0043_pub83_brand_kit'),
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitorPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=160, verbose_name='Nom du concurrent')),
                ('page_id', models.CharField(blank=True, default='', max_length=64, verbose_name='ID de Page Meta (view_all_page_id)')),
                ('country', models.CharField(default='MA', max_length=2, verbose_name='Pays (ISO-2)')),
                ('website', models.CharField(blank=True, default='', max_length=255, verbose_name='Site web')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('active', models.BooleanField(default=True, verbose_name='Suivi actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Page concurrente (veille)',
                'verbose_name_plural': 'Pages concurrentes (veille)',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CompetitorAdObservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('observed_at', models.DateField(verbose_name="Date d'observation")),
                ('hook_text', models.TextField(blank=True, default='', verbose_name='Accroche observée (reformulée)')),
                ('angle', models.CharField(blank=True, default='', max_length=120, verbose_name='Angle')),
                ('format', models.CharField(blank=True, default='', max_length=40, verbose_name='Format')),
                ('source_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Lien Ad Library (profond)')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('competitor_page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='observations', to='adsengine.competitorpage', verbose_name='Page concurrente')),
            ],
            options={
                'verbose_name': 'Observation concurrente (veille)',
                'verbose_name_plural': 'Observations concurrentes (veille)',
                'ordering': ['-observed_at', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='competitoradobservation',
            index=models.Index(fields=['company', 'competitor_page', 'observed_at'], name='adseng_compobs_co_page_idx'),
        ),
        migrations.AddConstraint(
            model_name='competitorpage',
            constraint=models.UniqueConstraint(fields=['company', 'name'], name='uniq_adseng_competpage_co_name'),
        ),
    ]
