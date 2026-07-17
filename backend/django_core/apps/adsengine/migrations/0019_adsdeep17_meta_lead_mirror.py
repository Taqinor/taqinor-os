import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP17 — MetaLeadMirror (leads Meta par ad) + unicité leadgen_id."""

    dependencies = [
        ('adsengine', '0018_adsdeep11_ad_creative_mirror'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetaLeadMirror',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('leadgen_id', models.CharField(
                    max_length=64, verbose_name='ID lead Meta')),
                ('ad_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID ad')),
                ('adset_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID ad set')),
                ('campaign_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID campagne')),
                ('form_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID formulaire')),
                ('created_time', models.DateTimeField(
                    blank=True, null=True, verbose_name='Créé le (Meta)')),
                ('is_organic', models.BooleanField(
                    default=False, verbose_name='Lead organique (sans ad)')),
                ('phone_key', models.CharField(
                    blank=True, default='', max_length=32,
                    verbose_name='Clé téléphone normalisée')),
                ('crm_lead_id', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='ID lead CRM')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Miroir de lead Meta',
                'verbose_name_plural': 'Miroirs de leads Meta',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='metaleadmirror',
            constraint=models.UniqueConstraint(
                fields=('company', 'leadgen_id'), name='uniq_adseng_meta_lead'),
        ),
        migrations.AddIndex(
            model_name='metaleadmirror',
            index=models.Index(
                fields=['company', 'ad_id'], name='adseng_mlead_co_ad_idx'),
        ),
        migrations.AddIndex(
            model_name='metaleadmirror',
            index=models.Index(
                fields=['company', 'phone_key'],
                name='adseng_mlead_co_ph_idx'),
        ),
    ]
