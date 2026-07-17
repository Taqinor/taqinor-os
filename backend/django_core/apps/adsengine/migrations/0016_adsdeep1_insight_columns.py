from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP1 — colonnes typées additives sur InsightSnapshot (diffusion +
    conversion + métriques vidéo). ADDITIVE : les rows existants gardent NULL."""

    dependencies = [
        ('adsengine', '0015_metaconnection_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='insightsnapshot',
            name='impressions',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Impressions'),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='reach',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Portée (reach)'),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='clicks',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Clics'),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='link_clicks',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Clics sur lien'),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='conversations',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Conversations WhatsApp'),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='leads_count',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Leads'),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='video_metrics',
            field=models.JSONField(
                blank=True, default=dict, verbose_name='Métriques vidéo'),
        ),
    ]
