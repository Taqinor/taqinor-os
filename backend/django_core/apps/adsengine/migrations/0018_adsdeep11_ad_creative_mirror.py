import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP11 — Miroir du créatif LIVE d'une ad (OneToOne AdMirror)."""

    dependencies = [
        ('adsengine', '0017_adsdeep7_insight_breakdown'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdCreativeMirror',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('creative_meta_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID créatif Meta')),
                ('body', models.TextField(
                    blank=True, default='', verbose_name='Texte principal')),
                ('title', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Titre')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('cta_type', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='Type de CTA')),
                ('link_url', models.TextField(
                    blank=True, default='', verbose_name='Lien')),
                ('image_hash', models.CharField(
                    blank=True, default='', max_length=128,
                    verbose_name='Hash image (permanent)')),
                ('video_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID vidéo (permanent)')),
                ('instagram_permalink_url', models.TextField(
                    blank=True, default='', verbose_name='Permalien Instagram')),
                ('effective_object_story_id', models.CharField(
                    blank=True, default='', max_length=128,
                    verbose_name='ID post de Page diffusé')),
                ('asset_feed_spec', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Spéc. créatif dynamique (peut être incomplète)')),
                ('fetched_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Récupéré le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('ad', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='creative_mirror', to='adsengine.admirror',
                    verbose_name='Ad')),
            ],
            options={
                'verbose_name': 'Miroir de créatif',
                'verbose_name_plural': 'Miroirs de créatif',
                'ordering': ['-created_at'],
            },
        ),
    ]
