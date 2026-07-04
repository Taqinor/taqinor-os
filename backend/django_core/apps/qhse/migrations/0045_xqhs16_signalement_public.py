import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.qhse.models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0044_xqhs15_diffusion_procedure'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LienSignalementPublic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chantier_id', models.PositiveIntegerField(verbose_name='ID du chantier')),
                ('token', models.CharField(default=apps.qhse.models._default_qr_token, editable=False, max_length=64, unique=True, verbose_name='Jeton')),
                ('libelle', models.CharField(blank=True, default='', max_length=255, verbose_name='Libellé (ex. nom du chantier)')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_liens_signalement', to='authentication.company', verbose_name='Société')),
                ('responsable_hse', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_liens_signalement_responsable', to=settings.AUTH_USER_MODEL, verbose_name='Responsable HSE à notifier')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_liens_signalement_crees', to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'Lien de signalement public (QR)',
                'verbose_name_plural': 'Liens de signalement public (QR)',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='SignalementPublic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_signalement', models.CharField(choices=[('danger', 'Danger'), ('incident', 'Incident')], default='danger', max_length=10, verbose_name='Type')),
                ('description', models.TextField(verbose_name='Description')),
                ('photo_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Photo (URL)')),
                ('nom', models.CharField(blank=True, default='', max_length=120, verbose_name='Nom (facultatif)')),
                ('telephone', models.CharField(blank=True, default='', max_length=40, verbose_name='Téléphone (facultatif)')),
                ('source', models.CharField(choices=[('qr_public', 'QR public')], default='qr_public', max_length=15, verbose_name='Source')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_signalements_publics', to='authentication.company', verbose_name='Société')),
                ('lien', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signalements', to='qhse.liensignalementpublic', verbose_name='Lien')),
                ('incident', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='signalements_publics', to='qhse.incident', verbose_name='Incident lié')),
            ],
            options={
                'verbose_name': 'Signalement public (QR)',
                'verbose_name_plural': 'Signalements publics (QR)',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='liensignalementpublic',
            index=models.Index(fields=['token'], name='qhse_liensig_token'),
        ),
        migrations.AddIndex(
            model_name='liensignalementpublic',
            index=models.Index(fields=['company', 'chantier_id'], name='qhse_liensig_co_chant'),
        ),
        migrations.AddIndex(
            model_name='signalementpublic',
            index=models.Index(fields=['company', 'type_signalement'], name='qhse_sigpub_co_type'),
        ),
    ]
