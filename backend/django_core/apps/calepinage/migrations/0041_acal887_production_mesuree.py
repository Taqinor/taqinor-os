"""ACAL887 — la production MESURÉE d'un calepinage (douze mois, kWh livrés).

Additive et réversible : une table neuve, aucune donnée existante touchée.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0036_apfs66_appartenance_role'),
        ('calepinage', '0040_acal598_role_echafaudage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductionMesuree',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('annee', models.PositiveSmallIntegerField(verbose_name='Année')),
                ('mois', models.PositiveSmallIntegerField(verbose_name='Mois (1 à 12)')),
                ('kwh_mesure', models.DecimalField(decimal_places=3, max_digits=12, verbose_name='Énergie mesurée (kWh)')),
                ('saisi_le', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Saisi le')),
                ('calepinage', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='productions_mesurees', to='calepinage.calepinage', verbose_name='Calepinage')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('saisi_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calepinage_productions_mesurees', to=settings.AUTH_USER_MODEL, verbose_name='Saisi par')),
            ],
            options={
                'verbose_name': 'Production mesurée',
                'verbose_name_plural': 'Productions mesurées',
                'ordering': ['annee', 'mois'],
                'indexes': [models.Index(fields=['company', 'calepinage'], name='cal_prm_co_cal_idx')],
                'constraints': [models.UniqueConstraint(fields=('calepinage', 'annee', 'mois'), name='uniq_production_mesuree_mois')],
            },
        ),
    ]
