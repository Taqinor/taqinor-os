import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0037_xqhs8_registre_exigences_legales'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Certification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referentiel', models.CharField(choices=[('iso_9001', 'ISO 9001'), ('iso_14001', 'ISO 14001'), ('iso_45001', 'ISO 45001'), ('nm', 'NM (norme marocaine)'), ('autre', 'Autre')], default='iso_9001', max_length=15, verbose_name='Référentiel')),
                ('organisme', models.CharField(blank=True, default='', max_length=255, verbose_name='Organisme')),
                ('numero_certificat', models.CharField(blank=True, default='', max_length=120, verbose_name='Numéro de certificat')),
                ('perimetre', models.TextField(blank=True, default='', verbose_name='Périmètre')),
                ('date_emission', models.DateField(blank=True, null=True, verbose_name="Date d'émission")),
                ('date_expiration', models.DateField(blank=True, null=True, verbose_name="Date d'expiration")),
                ('prealerte_jours', models.PositiveIntegerField(default=60, verbose_name='Préalerte (jours)')),
                ('statut', models.CharField(choices=[('valide', 'Valide'), ('a_renouveler', 'À renouveler'), ('expire', 'Expiré'), ('suspendu', 'Suspendu')], default='valide', max_length=15, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_certifications', to='authentication.company', verbose_name='Société')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_certifications', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
            ],
            options={
                'verbose_name': 'Certification',
                'verbose_name_plural': 'Certifications',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='AuditCertification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_etape', models.CharField(choices=[('etape_1', 'Étape 1'), ('etape_2', 'Étape 2'), ('surveillance', 'Surveillance'), ('renouvellement', 'Renouvellement')], default='surveillance', max_length=15, verbose_name='Type')),
                ('date_audit', models.DateField(blank=True, null=True, verbose_name="Date de l'audit")),
                ('auditeur_externe', models.CharField(blank=True, default='', max_length=255, verbose_name='Auditeur externe')),
                ('constats', models.TextField(blank=True, default='', verbose_name='Constats')),
                ('constat_majeur', models.BooleanField(default=False, verbose_name='Constat majeur')),
                ('ncr_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de la NCR levée')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('certification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audits', to='qhse.certification', verbose_name='Certification')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_audits_certification', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Audit de certification',
                'verbose_name_plural': 'Audits de certification',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='certification',
            index=models.Index(fields=['company', 'date_expiration'], name='qhse_certif_co_exp'),
        ),
    ]
