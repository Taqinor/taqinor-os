import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    """XFSM23 — géolocalisation temps réel + géofencing techniciens (ENFORCED,
    pas un opt-in : le consentement est déjà obtenu en amont, cf. la note de
    module dans models_gps_tracking.py). Additive — aucune migration
    destructive."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('installations', '0090_remove_astreinte_idx_astreinte_co_dates_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GpsConsentRecord',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('consent_ref', models.CharField(
                    blank=True, max_length=120, null=True)),
                ('consent_recorded_at', models.DateTimeField(
                    default=timezone.now)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_reason', models.CharField(
                    blank=True, max_length=255, null=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gps_consent_records',
                    to='authentication.company')),
                ('recorded_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='gps_consents_enregistres',
                    to=settings.AUTH_USER_MODEL)),
                ('technicien', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gps_consent_records',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Consentement GPS technicien',
                'verbose_name_plural': 'Consentements GPS technicien',
                'ordering': ['-consent_recorded_at'],
            },
        ),
        migrations.CreateModel(
            name='PositionTechnicien',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('lat', models.DecimalField(decimal_places=6, max_digits=9)),
                ('lng', models.DecimalField(decimal_places=6, max_digits=9)),
                ('accuracy_m', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True)),
                ('captured_at', models.DateTimeField(default=timezone.now)),
                ('distance_site_km', models.DecimalField(
                    blank=True, decimal_places=3, max_digits=8, null=True)),
                ('hors_perimetre', models.BooleanField(default=False)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='positions_techniciens',
                    to='authentication.company')),
                ('intervention', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='positions_gps',
                    to='installations.intervention')),
                ('technicien', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='positions_gps',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Position technicien',
                'verbose_name_plural': 'Positions techniciens',
                'ordering': ['-captured_at'],
            },
        ),
        migrations.CreateModel(
            name='GeofenceAlert',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('distance_site_km', models.DecimalField(
                    decimal_places=3, max_digits=8)),
                ('rayon_attendu_km', models.DecimalField(
                    decimal_places=3, max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('acquittee', models.BooleanField(default=False)),
                ('acquittee_le', models.DateTimeField(blank=True, null=True)),
                ('acquittee_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='geofence_alerts_acquittees',
                    to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='geofence_alerts',
                    to='authentication.company')),
                ('intervention', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='geofence_alerts',
                    to='installations.intervention')),
                ('position', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='geofence_alerts',
                    to='installations.positiontechnicien')),
                ('technicien', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='geofence_alerts',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Alerte géofence',
                'verbose_name_plural': 'Alertes géofence',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='gpsconsentrecord',
            index=models.Index(
                fields=['company', 'technicien'],
                name='inst_gpsconsent_co_tech_idx'),
        ),
        migrations.AddConstraint(
            model_name='gpsconsentrecord',
            constraint=models.UniqueConstraint(
                condition=models.Q(('revoked_at__isnull', True)),
                fields=('company', 'technicien'),
                name='uniq_gps_consent_actif'),
        ),
        migrations.AddIndex(
            model_name='positiontechnicien',
            index=models.Index(
                fields=['company', 'technicien', '-captured_at'],
                name='inst_postech_co_tech_cap_idx'),
        ),
        migrations.AddIndex(
            model_name='positiontechnicien',
            index=models.Index(
                fields=['intervention', '-captured_at'],
                name='inst_postech_interv_cap_idx'),
        ),
        migrations.AddIndex(
            model_name='geofencealert',
            index=models.Index(
                fields=['company', 'intervention', '-created_at'],
                name='inst_geofence_co_iv_crt_idx'),
        ),
    ]
