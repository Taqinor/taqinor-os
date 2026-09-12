# NTNRG27 — Registre des certificats carbone émis (additive, hand-written).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('monitoring', '0005_ntnrg14_sladisponibilite'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificatCarbone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('installation_id', models.PositiveIntegerField(blank=True, help_text="Id de l'installation (certificat PAR SITE). XOR client_id.", null=True)),
                ('client_id', models.PositiveIntegerField(blank=True, help_text='Id du client (certificat CONSOLIDÉ multi-sites). XOR installation_id.', null=True)),
                ('periode_debut', models.DateField()),
                ('periode_fin', models.DateField()),
                ('tco2_evitees', models.DecimalField(decimal_places=3, max_digits=12)),
                ('reference', models.CharField(max_length=50)),
                ('fichier_key', models.CharField(blank=True, default='', max_length=500)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='certificats_carbone', to='authentication.company')),
            ],
            options={
                'verbose_name': 'Certificat carbone',
                'verbose_name_plural': 'Certificats carbone',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='certificatcarbone',
            index=models.Index(fields=['company', 'installation_id'], name='monitoring_certifco2_site_idx'),
        ),
        migrations.AddIndex(
            model_name='certificatcarbone',
            index=models.Index(fields=['company', 'client_id'], name='monitoring_certifco2_cli_idx'),
        ),
        migrations.AddConstraint(
            model_name='certificatcarbone',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(('installation_id__isnull', False), ('client_id__isnull', True))
                    | models.Q(('installation_id__isnull', True), ('client_id__isnull', False))
                ),
                name='monitoring_certifco2_xor_cible',
            ),
        ),
        migrations.AddConstraint(
            model_name='certificatcarbone',
            constraint=models.UniqueConstraint(
                condition=models.Q(('installation_id__isnull', False)),
                fields=('company', 'installation_id', 'periode_debut', 'periode_fin'),
                name='monitoring_certifco2_site_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='certificatcarbone',
            constraint=models.UniqueConstraint(
                condition=models.Q(('client_id__isnull', False)),
                fields=('company', 'client_id', 'periode_debut', 'periode_fin'),
                name='monitoring_certifco2_cli_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='certificatcarbone',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='monitoring_certifco2_reference_uniq',
            ),
        ),
    ]
