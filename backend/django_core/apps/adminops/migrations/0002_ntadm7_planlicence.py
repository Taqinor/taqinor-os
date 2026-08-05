# NTADM7 — Catalogue des paliers de licence TAQINOR (starter/pro/enterprise).
# GLOBAL (pas de FK company) : ce catalogue appartient à TAQINOR, pas à un
# tenant. Additif, aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminops', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanLicence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(choices=[('starter', 'Starter'), ('pro', 'Pro'), ('enterprise', 'Enterprise')], help_text='Palier commercial (starter/pro/enterprise).', max_length=20, unique=True)),
                ('nom', models.CharField(max_length=100)),
                ('modules_inclus', models.JSONField(blank=True, default=list, help_text="Clés de module (AppConfig.module_manifest['key']) incluses dans ce palier — ex. ['crm', 'ventes', 'stock'].")),
                ('actif', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Plan de licence',
                'verbose_name_plural': 'Plans de licence',
                'ordering': ['id'],
            },
        ),
    ]
