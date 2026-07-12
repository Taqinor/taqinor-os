import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """NTPLT7 — limites douces par tenant : modèle ``TenantLimit`` (company,
    cle parmi max_lignes_table/max_stockage_mo/max_exports_jour, valeur ;
    0 = illimité). Enforcement DOUX (notification + en-tête, jamais de
    blocage)."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0030_ntplt41_sequencecounter'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantLimit',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cle', models.CharField(
                    choices=[
                        ('max_lignes_table', 'Lignes maximum par table'),
                        ('max_stockage_mo', 'Stockage maximum (Mo)'),
                        ('max_exports_jour', 'Exports maximum par jour'),
                    ],
                    max_length=32, verbose_name='Clé')),
                ('valeur', models.BigIntegerField(
                    default=0, help_text='Plafond (0 = illimité).',
                    verbose_name='Valeur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Limite tenant',
                'verbose_name_plural': 'Limites tenant',
                'ordering': ['company_id', 'cle'],
            },
        ),
        migrations.AddConstraint(
            model_name='tenantlimit',
            constraint=models.UniqueConstraint(
                fields=['company', 'cle'],
                name='core_tenantlimit_company_cle'),
        ),
    ]
