"""DC12 — SiteProfile : profil site/énergie RÉUTILISABLE par client.

Additif : nouvelle table, aucune colonne existante modifiée. Company-scoped via
FK ; OneToOne vers crm.Client (une seule fiche par client). Source unique du
profil site/énergie/toiture, pré-rempli par le générateur de devis (y compris
les devis sans lead). Les choix (raccordement, type d'installation, type de
toiture, orientation, ombrage) réutilisent STRICTEMENT le vocabulaire des enums
``Lead`` — aucune nouvelle liste de valeurs.
"""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0030_pointcontact'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteProfile',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('facture_hiver', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True)),
                ('facture_ete', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True)),
                ('ete_differente', models.BooleanField(default=False)),
                ('conso_mensuelle_kwh', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True)),
                ('tranche_onee', models.CharField(
                    max_length=100, blank=True, null=True)),
                ('raccordement', models.CharField(
                    choices=[
                        ('monophase', 'Monophasé'),
                        ('triphase', 'Triphasé'),
                        ('inconnu', 'Je ne sais pas'),
                    ],
                    max_length=12, blank=True, null=True)),
                ('regularisation_8221', models.BooleanField(default=False)),
                ('type_installation', models.CharField(
                    choices=[
                        ('residentiel', 'Résidentiel'),
                        ('commercial', 'Commercial'),
                        ('industriel', 'Industriel'),
                        ('agricole', 'Agricole'),
                    ],
                    max_length=20, blank=True, null=True)),
                ('pompe_cv', models.DecimalField(
                    max_digits=6, decimal_places=2, null=True, blank=True)),
                ('pompe_hmt_m', models.DecimalField(
                    max_digits=8, decimal_places=2, null=True, blank=True)),
                ('pompe_debit_m3h', models.DecimalField(
                    max_digits=8, decimal_places=2, null=True, blank=True)),
                ('type_toiture', models.CharField(
                    choices=[
                        ('terrasse_beton', 'Terrasse béton'),
                        ('tole_metal', 'Tôle/Métal'),
                        ('tuiles', 'Tuiles'),
                        ('bac_acier', 'Bac acier'),
                        ('fibrociment', 'Fibrociment'),
                        ('autre', 'Autre'),
                    ],
                    max_length=20, blank=True, null=True)),
                ('surface_toiture_m2', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True)),
                ('orientation', models.CharField(
                    choices=[
                        ('sud', 'Sud'),
                        ('sud_est', 'Sud-Est'),
                        ('sud_ouest', 'Sud-Ouest'),
                        ('est', 'Est'),
                        ('ouest', 'Ouest'),
                        ('autre', 'Autre'),
                    ],
                    max_length=12, blank=True, null=True)),
                ('inclinaison_deg', models.DecimalField(
                    max_digits=5, decimal_places=2, null=True, blank=True)),
                ('ombrage', models.CharField(
                    choices=[
                        ('aucun', 'Aucun'),
                        ('partiel', 'Partiel'),
                        ('important', 'Important'),
                    ],
                    max_length=12, blank=True, null=True)),
                ('ombrage_notes', models.TextField(blank=True, null=True)),
                ('gps_lat', models.DecimalField(
                    max_digits=9, decimal_places=6, null=True, blank=True,
                    validators=[
                        django.core.validators.MinValueValidator(-90),
                        django.core.validators.MaxValueValidator(90)])),
                ('gps_lng', models.DecimalField(
                    max_digits=9, decimal_places=6, null=True, blank=True,
                    validators=[
                        django.core.validators.MinValueValidator(-180),
                        django.core.validators.MaxValueValidator(180)])),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='site_profiles',
                    to='authentication.company',
                )),
                ('client', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='site_profile',
                    to='crm.client',
                    verbose_name='Client',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Profil site',
                'verbose_name_plural': 'Profils site',
                'ordering': ['-date_modification'],
            },
        ),
    ]
