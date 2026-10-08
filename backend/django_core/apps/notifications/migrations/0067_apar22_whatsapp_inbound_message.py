"""APAR22 — table d'idempotence des messages WhatsApp BSP entrants (additive)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0010_customuser_supervisor'),
        ('notifications', '0066_n1_notification_programmee_pour_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppInboundMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('wa_message_id', models.CharField(max_length=255, verbose_name='ID message WhatsApp (wamid)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Message WhatsApp entrant',
                'verbose_name_plural': 'Messages WhatsApp entrants',
                'constraints': [models.UniqueConstraint(fields=('company', 'wa_message_id'), name='nwa_inbound_company_wamid_uniq')],
            },
        ),
    ]
