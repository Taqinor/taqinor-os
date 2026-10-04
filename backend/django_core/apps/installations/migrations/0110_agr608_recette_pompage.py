"""AGR608 — fiche de recette POMPAGE (cadre IEC 62253:2011) : nouveau modèle
``RecettePompage`` (OneToOne chantier, scopé société). ADDITIF pur et
réversible — aucune table existante modifiée."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
        ('installations', '0109_agr602_regime_hors_reseau'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecettePompage',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('date_essai', models.DateField(blank=True, null=True)),
                ('instrument_id', models.CharField(
                    blank=True, default='', max_length=60)),
                ('niveau_statique_m', models.FloatField(blank=True, null=True)),
                ('niveau_dynamique_m', models.FloatField(
                    blank=True, null=True)),
                ('hmt_mesuree_m', models.FloatField(blank=True, null=True)),
                ('debit_mesure_m3h', models.FloatField(blank=True, null=True)),
                ('methode_debit', models.CharField(
                    blank=True,
                    choices=[('compteur', 'Compteur'),
                             ('jaugeage', 'Jaugeage')],
                    default='', max_length=10)),
                ('index_compteur_m3', models.FloatField(blank=True, null=True)),
                ('courant_plaque_a', models.FloatField(blank=True, null=True)),
                ('courant_phase_1_a', models.FloatField(blank=True, null=True)),
                ('courant_phase_2_a', models.FloatField(blank=True, null=True)),
                ('courant_phase_3_a', models.FloatField(blank=True, null=True)),
                ('tension_v', models.PositiveIntegerField(
                    blank=True, null=True)),
                ('frequence_variateur_hz', models.FloatField(
                    blank=True, null=True)),
                ('irradiance_wm2', models.PositiveIntegerField(
                    blank=True, null=True)),
                ('source_irradiance', models.CharField(
                    blank=True,
                    choices=[('mesuree', 'Mesurée'), ('estimee', 'Estimée')],
                    default='', max_length=8)),
                ('isolement_moteur_mohm', models.FloatField(
                    blank=True, null=True)),
                ('isolement_ok', models.BooleanField(blank=True, null=True)),
                ('sens_rotation_ok', models.BooleanField(
                    blank=True, null=True)),
                ('test_marche_a_sec_ok', models.BooleanField(
                    blank=True, null=True)),
                ('resultat', models.CharField(
                    choices=[('en_cours', 'En cours'),
                             ('conforme', 'Conforme'),
                             ('reserves', 'Conforme avec réserves'),
                             ('non_conforme', 'Non conforme')],
                    default='en_cours', max_length=14)),
                ('observations', models.TextField(blank=True, default='')),
                ('commentaire_ecart', models.TextField(
                    blank=True, default='')),
                ('promesse', models.JSONField(blank=True, default=dict)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recettes_pompage',
                    to='authentication.company')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recettes_pompage_creees',
                    to=settings.AUTH_USER_MODEL)),
                ('installation', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recette_pompage',
                    to='installations.installation')),
                ('technicien', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recettes_pompage_technicien',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Recette pompage (IEC 62253)',
                'verbose_name_plural': 'Recettes pompage (IEC 62253)',
                'ordering': ['-date_creation'],
            },
        ),
    ]
