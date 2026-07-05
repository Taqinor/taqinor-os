from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('flotte', '0047_remove_accusecharte_flotte_accusecharte_co_cond_ver_uniq_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZoneGeographique',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=120, verbose_name='Nom de la zone')),
                ('type_zone', models.CharField(choices=[('depot', 'Dépôt'), ('chantier', 'Chantier'), ('interdite', 'Zone interdite')], default='depot', max_length=10, verbose_name='Type de zone')),
                ('centre_lat', models.DecimalField(decimal_places=6, max_digits=9, verbose_name='Latitude du centre')),
                ('centre_lng', models.DecimalField(decimal_places=6, max_digits=9, verbose_name='Longitude du centre')),
                ('rayon_metres', models.PositiveIntegerField(verbose_name='Rayon (mètres)')),
                ('heure_debut_autorisee', models.TimeField(blank=True, null=True, verbose_name='Heure de début autorisée')),
                ('heure_fin_autorisee', models.TimeField(blank=True, null=True, verbose_name='Heure de fin autorisée')),
                ('actif', models.BooleanField(default=True, verbose_name='Active')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flotte_zones_geographiques', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Zone géographique',
                'verbose_name_plural': 'Zones géographiques',
                'ordering': ['nom'],
            },
        ),
        migrations.AddIndex(
            model_name='zonegeographique',
            index=models.Index(fields=['company', 'type_zone'], name='flotte_zone_co_type_idx'),
        ),
        migrations.AddIndex(
            model_name='zonegeographique',
            index=models.Index(fields=['company', 'actif'], name='flotte_zone_co_act_idx'),
        ),
    ]
