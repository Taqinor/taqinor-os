# NTWMS39 — journal léger du plan d'entrepôt (historique de casier).
# Additive : une nouvelle table, aucune colonne touchée sur l'existant.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('installations', '0100_photochecklistmeta_tenantmodel_timestamps'),
        ('stock', '0109_ntwms38_hazmat'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoriqueCasier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('action', models.CharField(choices=[('creation', 'Création'), ('modification', 'Modification'), ('archivage', 'Archivage'), ('reactivation', 'Réactivation')], max_length=20)),
                ('champ', models.CharField(blank=True, default='', max_length=40)),
                ('ancienne_valeur', models.CharField(blank=True, default='', max_length=200)),
                ('nouvelle_valeur', models.CharField(blank=True, default='', max_length=200)),
                ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='historiques_casier_stock', to=settings.AUTH_USER_MODEL)),
                ('bin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historique_stock', to='installations.binlocation')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Historique de casier',
                'verbose_name_plural': 'Historiques de casier',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['company', 'bin'], name='idx_histcasier_co_bin')],
            },
        ),
    ]
