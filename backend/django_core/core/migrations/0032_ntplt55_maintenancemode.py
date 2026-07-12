from django.db import migrations, models


class Migration(migrations.Migration):
    """NTPLT55 — mode lecture seule (maintenance) : singleton ``MaintenanceMode``
    (actif + message) activable à chaud, consommé par le middleware pour
    répondre 503 aux écritures pendant une bascule de schéma."""

    dependencies = [
        ('core', '0031_ntplt7_tenantlimit'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceMode',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actif', models.BooleanField(
                    default=False, verbose_name='Maintenance active')),
                ('message', models.CharField(
                    default='Maintenance en cours, réessayez dans quelques '
                            'instants.',
                    max_length=255, verbose_name='Message')),
            ],
            options={
                'verbose_name': 'Mode maintenance',
                'verbose_name_plural': 'Mode maintenance',
            },
        ),
    ]
