import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """NTPLT9/10 — bus d'événements fiable : ``OutboxEvent`` (outbox
    transactionnel, statuts pending/delivered/failed/dead, retries) +
    ``ProcessedEvent`` (dédup consommateur par event_id+handler)."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0033_ntplt29_backgroundjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutboxEvent',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_name', models.CharField(
                    max_length=100, verbose_name='Événement')),
                ('payload', models.JSONField(
                    blank=True, default=dict, verbose_name='Payload')),
                ('event_id', models.UUIDField(
                    default=uuid.uuid4, editable=False, unique=True,
                    verbose_name='Event ID')),
                ('occurred_at', models.DateTimeField(
                    default=django.utils.timezone.now,
                    verbose_name='Survenu le')),
                ('statut', models.CharField(
                    choices=[
                        ('pending', 'En attente'), ('delivered', 'Livré'),
                        ('failed', 'En échec (à réessayer)'),
                        ('dead', 'Abandonné (dead-letter)'),
                    ],
                    db_index=True, default='pending', max_length=12,
                    verbose_name='Statut')),
                ('tentatives', models.PositiveIntegerField(
                    default=0, verbose_name='Tentatives')),
                ('prochaine_tentative', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Prochaine tentative')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='outbox_events',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Événement outbox',
                'verbose_name_plural': 'Événements outbox',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProcessedEvent',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_id', models.UUIDField(verbose_name='Event ID')),
                ('handler_name', models.CharField(
                    max_length=200, verbose_name='Handler')),
            ],
            options={
                'verbose_name': 'Événement traité',
                'verbose_name_plural': 'Événements traités',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(
                fields=['statut', 'prochaine_tentative'],
                name='core_outbox_statut_next_idx'),
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(
                fields=['event_name', '-created_at'],
                name='core_outbox_name_idx'),
        ),
        migrations.AddConstraint(
            model_name='processedevent',
            constraint=models.UniqueConstraint(
                fields=['event_id', 'handler_name'],
                name='core_processedevent_evt_handler'),
        ),
    ]
