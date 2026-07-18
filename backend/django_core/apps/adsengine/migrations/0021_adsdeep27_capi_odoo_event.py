import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP27/28 — CapiOdooEvent : marqueur d'idempotence des événements CAPI
    CRM-Dataset (lead_received + signed_contract) + unicité (company, event_key)."""

    dependencies = [
        ('adsengine', '0020_adsdeep24_ctwa_referral'),
    ]

    operations = [
        migrations.CreateModel(
            name='CapiOdooEvent',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_key', models.CharField(
                    max_length=200, verbose_name="Clé d'événement (dedup)")),
                ('event_name', models.CharField(
                    max_length=64, verbose_name="Nom d'événement Meta")),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Événement CAPI Odoo émis',
                'verbose_name_plural': 'Événements CAPI Odoo émis',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='capiodooevent',
            constraint=models.UniqueConstraint(
                fields=('company', 'event_key'),
                name='uniq_adseng_capi_odoo_event'),
        ),
    ]
