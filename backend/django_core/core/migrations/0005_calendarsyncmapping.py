# FG374 — Sync calendrier Google/Outlook (2-way) : table de correspondance.
#
# Ajoute ``CalendarSyncMapping`` : associe l'identité GÉNÉRIQUE d'un événement
# local (local_kind + local_id, sans FK métier) à son équivalent externe —
# AUCUN import d'app métier (contrat import-linter
# ``core-foundation-is-a-base-layer``). Migration ADDITIVE et réversible.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('core', '0004_esignrequest'),
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarSyncMapping',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('provider', models.CharField(
                    max_length=60, verbose_name='Fournisseur')),
                ('local_kind', models.CharField(
                    help_text="Catégorie d'événement local, ex. "
                              "« intervention ».",
                    max_length=40, verbose_name='Type local')),
                ('local_id', models.CharField(
                    max_length=64, verbose_name='Identifiant local')),
                ('external_event_id', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Identifiant externe')),
                ('external_calendar_id', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Calendrier externe')),
                ('last_hash', models.CharField(
                    blank=True, default='',
                    help_text='Hash du dernier état synchronisé (détection de '
                              'diff).',
                    max_length=64, verbose_name='Empreinte')),
                ('last_synced_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Dernière synchro')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='calendar_sync_mappings',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Correspondance calendrier',
                'verbose_name_plural': 'Correspondances calendrier',
                'ordering': ['-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='calendarsyncmapping',
            constraint=models.UniqueConstraint(
                fields=('company', 'provider', 'local_kind', 'local_id'),
                name='core_calsync_co_prov_local'),
        ),
        migrations.AddIndex(
            model_name='calendarsyncmapping',
            index=models.Index(
                fields=['company', 'provider'],
                name='core_calsync_co_prov_idx'),
        ),
        migrations.AddIndex(
            model_name='calendarsyncmapping',
            index=models.Index(
                fields=['provider', 'external_event_id'],
                name='core_calsync_ext_idx'),
        ),
    ]
