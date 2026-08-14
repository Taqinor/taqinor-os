"""PV5 — FicheTechnique étendue : `type_fiche` + blocs de champs optionnels
module/onduleur/batterie (dimensions, coefficients de température, MPPT,
capacité, DoD…), tous nullable/blank. Additif pur, aucune colonne existante
touchée ; les fiches déjà en base restent inchangées (`type_fiche=''`)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0085_ntadm2_produit_entite'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_dod_pct',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Profondeur de décharge (DoD, %).', max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_kwh_nominal',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Capacité nominale (kWh).', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_kwh_usable',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Capacité utilisable (kWh).', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_max_charge_kw',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Puissance de charge maximale (kW).', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_v_nominal',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Tension nominale (V).', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bifacial',
            field=models.BooleanField(default=False, help_text='Module bifacial (production face arrière).'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='epaisseur_mm',
            field=models.PositiveIntegerField(blank=True, help_text='Épaisseur du module (mm).', null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='largeur_mm',
            field=models.PositiveIntegerField(blank=True, help_text='Largeur du module (mm).', null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='longueur_mm',
            field=models.PositiveIntegerField(blank=True, help_text='Longueur du module (mm).', null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_ac_kw',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Puissance AC nominale (kW).', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_i_max_mppt_a',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Courant maximal par entrée MPPT (A).', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_mppt_v_max',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Tension MPPT maximale (V).', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_mppt_v_min',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Tension MPPT minimale (V).', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_n_mppt',
            field=models.PositiveSmallIntegerField(blank=True, help_text="Nombre d'entrées MPPT.", null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_phases',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Monophasé'), (3, 'Triphasé')], help_text='Nombre de phases (1 = monophasé, 3 = triphasé).', null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_rendement_euro_pct',
            field=models.DecimalField(blank=True, decimal_places=1, help_text="Rendement européen de l'onduleur (%).", max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_v_max_abs',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Tension DC maximale absolue (V).', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='poids_kg',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Poids du module (kg).', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='techno_cellule',
            field=models.CharField(blank=True, default='', help_text='Technologie de cellule (ex. N-type TOPCon, PERC…).', max_length=100),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='temp_coeff_pmax_pct_c',
            field=models.DecimalField(blank=True, decimal_places=3, help_text='Coefficient de température de Pmax (%/°C).', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='temp_coeff_voc_pct_c',
            field=models.DecimalField(blank=True, decimal_places=3, help_text='Coefficient de température de Voc (%/°C).', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='type_fiche',
            field=models.CharField(blank=True, choices=[('module', 'Module (panneau)'), ('onduleur', 'Onduleur'), ('batterie', 'Batterie'), ('autre', 'Autre')], default='', help_text='Type de fiche technique (détermine les champs applicables).', max_length=16),
        ),
    ]
