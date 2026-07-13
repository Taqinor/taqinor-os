import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """YDATA12 — infra idempotence webhooks entrants : `ProcessedWebhookEvent`
    (company + source + event_id, contrainte unique) — insérée AVANT tout
    effet de bord par `core.idempotency.dedupe_event` (IntegrityError sur la
    2e arrivée concurrente/rejeu = "déjà traité")."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0034_ntplt9_outbox_processedevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessedWebhookEvent',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('source', models.CharField(max_length=100, verbose_name='Source')),
                ('event_id', models.CharField(max_length=200, verbose_name='Event ID')),
                ('created_at', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='core_processedwebhookevent_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Événement webhook traité',
                'verbose_name_plural': 'Événements webhook traités',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='processedwebhookevent',
            constraint=models.UniqueConstraint(
                fields=['company', 'source', 'event_id'],
                name='core_processedwebhookevent_unique'),
        ),
    ]
