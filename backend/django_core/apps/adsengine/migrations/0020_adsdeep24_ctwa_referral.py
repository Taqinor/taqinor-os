import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP24 — CtwaReferral (attribution CTWA par ad d'un message WhatsApp
    entrant) + unicité (company, wa_message_id)."""

    dependencies = [
        ('adsengine', '0019_adsdeep17_meta_lead_mirror'),
    ]

    operations = [
        migrations.CreateModel(
            name='CtwaReferral',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('wa_message_id', models.CharField(
                    max_length=128, verbose_name='ID message WhatsApp')),
                ('ad_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID ad (source_id)')),
                ('ctwa_clid', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Click ID CTWA')),
                ('source_type', models.CharField(
                    blank=True, default='', max_length=16,
                    verbose_name='Type de source (ad/post)')),
                ('headline', models.TextField(
                    blank=True, default='', verbose_name='Titre de la pub')),
                ('ts', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Horodatage du message')),
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
                'verbose_name': 'Référence CTWA',
                'verbose_name_plural': 'Références CTWA',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='ctwareferral',
            constraint=models.UniqueConstraint(
                fields=('company', 'wa_message_id'),
                name='uniq_adseng_ctwa_msg'),
        ),
        migrations.AddIndex(
            model_name='ctwareferral',
            index=models.Index(
                fields=['company', 'ad_id'], name='adseng_ctwa_co_ad_idx'),
        ),
        migrations.AddIndex(
            model_name='ctwareferral',
            index=models.Index(
                fields=['company', 'phone_key'],
                name='adseng_ctwa_co_ph_idx'),
        ),
    ]
