# PUB83 — Kit de marque persistant (BrandKit, OneToOne société) consommé par le
# TemplatedAdapter + champ thumbnail_key sur CreativeAsset (vignette CHOISIE,
# jamais la frame 0 ; vérifiée en warning à la check-list policy).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0042_pub78_creative_calendar_event'),
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.AddField(
            model_name='creativeasset',
            name='thumbnail_key',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Clé MinIO de la vignette'),
        ),
        migrations.CreateModel(
            name='BrandKit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(blank=True, default='', max_length=120, verbose_name='Nom du kit')),
                ('logo_key', models.CharField(blank=True, default='', max_length=255, verbose_name='Clé MinIO du logo')),
                ('colors', models.JSONField(blank=True, default=dict, help_text='Ex. {"primary": "#0A6", "secondary": "#111"}.', verbose_name='Couleurs')),
                ('safe_zones', models.JSONField(blank=True, default=dict, help_text='Marges/gabarits réservés (haut/bas/côtés) par format.', verbose_name='Zones de sécurité')),
                ('fonts', models.JSONField(blank=True, default=list, verbose_name='Polices')),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='adsengine_brand_kit', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Kit de marque',
                'verbose_name_plural': 'Kits de marque',
                'ordering': ['-created_at'],
            },
        ),
    ]
