import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """NTPLT6 — compteurs d'usage par tenant (metering) : instantané quotidien
    TenantUsageSnapshot (une ligne par (company, jour), idempotent). Fondation
    technique consommée plus tard par N100 (plans/billing, différé)."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0027_qx37_remove_webhooksubscription'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantUsageSnapshot',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('jour', models.DateField(
                    help_text="Jour de l'instantané (UTC).",
                    verbose_name='Jour')),
                ('lignes_par_table', models.JSONField(
                    blank=True, default=dict,
                    help_text="{ 'app_label.Model': nombre_de_lignes } pour "
                              "les grosses tables company-scopées (comptage "
                              "borné).",
                    verbose_name='Lignes par table')),
                ('octets_minio', models.BigIntegerField(
                    default=0,
                    help_text="Total d'octets stockés sous le préfixe société "
                              "dans MinIO (0 si le stockage est "
                              "indisponible).",
                    verbose_name='Octets MinIO')),
                ('nb_requetes_api', models.PositiveIntegerField(
                    default=0,
                    help_text="Somme des requêtes API (ApiUsageRecord) de la "
                              "société ce jour-là.",
                    verbose_name='Requêtes API du jour')),
                ('nb_taches_celery', models.PositiveIntegerField(
                    default=0,
                    help_text="Nombre de tâches Celery attribuables à la "
                              "société ce jour (0 si non instrumenté).",
                    verbose_name='Tâches Celery')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usage_snapshots',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Instantané d'usage",
                'verbose_name_plural': "Instantanés d'usage",
                'ordering': ['-jour', 'company_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='tenantusagesnapshot',
            constraint=models.UniqueConstraint(
                fields=['company', 'jour'],
                name='core_tenantusage_company_jour'),
        ),
        migrations.AddIndex(
            model_name='tenantusagesnapshot',
            index=models.Index(
                fields=['company', '-jour'],
                name='core_tenantusage_co_jour_idx'),
        ),
    ]
