"""NTSUB27 — Cache nocturne des metriques SaaS (ARR bridge / Quick Ratio /
Rule of 40).

NTSUB12 recalcule ces agregats A LA VOLEE a chaque ouverture du cockpit :
couteux sur plusieurs annees d'historique. Un job nocturne remplit cette table
une fois par societe et par mois ; l'endpoint lit le cache s'il a moins de
24 h et retombe SILENCIEUSEMENT sur le calcul a la volee sinon.

Purement ADDITIF (creation de table) et revertable : aucune donnee existante
n'est touchee, et un cache absent ne change rien au comportement actuel.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('contrats', '0052_ntsub26_compteur_usage_archive'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetriquesSaasCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('periode', models.CharField(max_length=7, verbose_name='Période (AAAA-MM)')),
                ('arr_bridge', models.JSONField(blank=True, default=dict, verbose_name='ARR bridge')),
                ('quick_ratio', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True, verbose_name='Quick Ratio')),
                ('rule_of_40', models.JSONField(blank=True, default=dict, verbose_name='Rule of 40')),
                ('prevision_mrr', models.JSONField(blank=True, null=True, verbose_name='Prévision de MRR (NTSUB13)')),
                ('calcule_le', models.DateTimeField(verbose_name='Calculé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Cache de métriques SaaS',
                'verbose_name_plural': 'Caches de métriques SaaS',
                'ordering': ['-periode', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='metriquessaascache',
            constraint=models.UniqueConstraint(fields=('company', 'periode'), name='contrats_metriquessaas_uniq'),
        ),
    ]
