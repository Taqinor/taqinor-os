# CALX60 (21/09/2026) — LA SEULE migration `stock` du groupe CALX : tout ce
# que la chaîne de pertes séquentielle et l'électrique lisent sur une fiche
# technique, en UN passage.
#
# Trois propositions séparées (côté AC micro-onduleur, courbe de rendement
# onduleur, fiche batterie/optimiseur) se contredisaient sur le bloc « sortie
# d'optimiseur » : elles sont FUSIONNÉES ici. 22 colonnes, TOUTES nullables ou
# à chaîne vide, AUCUNE valeur par défaut métier — une fiche existante sort de
# cette migration exactement comme elle y est entrée, et l'étape qui lirait un
# champ vide s'OMET en le nommant plutôt que de forfaitiser (D-CALX 7).
# Purement additive : aucune donnée touchée, aucune contrainte posée.
#
# Deux demandes de l'énoncé ne créent PAS de colonne, et c'est volontaire :
#   * `ond_s_max_kva` (« si absent ») EXISTE déjà depuis CAL115 ;
#   * `bat_eol_pct` est la grandeur que porte déjà
#     `bat_retention_fin_de_vie_pct` (CAL118) — une seconde colonne aurait
#     donné deux vérités pour une seule donnée ; le sélecteur publie la clé
#     `eol_pct` depuis ce champ unique.
#
# DÉPENDANCE — l'en-tête du plan annonçait la tête `0158_ntp2p35_...`, mais
# `0159_solmvp12_detacher_flotte_qhse_rh` a été fusionnée depuis : c'est elle
# la feuille réelle. Dépendre de 0158 aurait laissé DEUX feuilles dans le
# graphe et fait échouer `makemigrations --check`. Le NOM de fichier reste
# celui que le plan nomme.

import apps.stock.models
import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0159_solmvp12_detacher_flotte_qhse_rh'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_c_rate_charge',
            field=models.DecimalField(blank=True, decimal_places=2, help_text="C-rate de CHARGE publié (ex. 0,50 C). Vide = non publié : il n'est jamais déduit des kW saisis.", max_digits=4, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_c_rate_decharge',
            field=models.DecimalField(blank=True, decimal_places=2, help_text="C-rate de DÉCHARGE publié (ex. 1,00 C). Vide = non publié : il n'est jamais déduit des kW saisis.", max_digits=4, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_chimie',
            field=models.CharField(blank=True, choices=[('lfp', 'LFP (lithium fer phosphate)'), ('nmc', 'NMC (lithium nickel manganèse cobalt)'), ('nca', 'NCA (lithium nickel cobalt aluminium)'), ('lmo', 'LMO (lithium manganèse)'), ('lto', 'LTO (titanate de lithium)'), ('plomb_ouvert', 'Plomb ouvert (à entretien)'), ('plomb_agm', 'Plomb AGM (étanche)'), ('plomb_gel', 'Plomb gel (étanche)'), ('autre', 'Autre (préciser sur la fiche produit)')], default='', help_text='Chimie de cellule publiée. Vide = non publiée.', max_length=16),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_temp_max_c',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Température de fonctionnement MAXIMALE publiée (°C). Vide = non publiée.', max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_temp_min_c',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Température de fonctionnement MINIMALE publiée (°C). Vide = non publiée.', max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_conso_nuit_w',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Consommation de NUIT / veille publiée (W). Énergie réellement soutirée, jamais un pourcentage. Vide = non publiée.', max_digits=7, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0'))]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_courbe_rendement',
            field=models.JSONField(blank=True, help_text='Courbe de rendement publiée : [{"charge_pct": 30, "rendement_pct": 97.2, "tension_v": 360}, …] — le rendement à chaque taux de charge, et la tension d\'entrée de la courbe (facultative : plusieurs courbes peuvent coexister, une par tension). Vide = non publiée.', null=True, validators=[apps.stock.models.valider_courbe_rendement_onduleur]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_rendement_cec_pct',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Rendement pondéré CEC publié (%, pondération californienne). Vide = non publié.', max_digits=4, null=True, validators=[django.core.validators.MinValueValidator(Decimal('1')), django.core.validators.MaxValueValidator(Decimal('100'))]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_rendement_max_pct',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Rendement MAXIMAL publié (%, « peak efficiency »). Vide = non publié.', max_digits=4, null=True, validators=[django.core.validators.MinValueValidator(Decimal('1')), django.core.validators.MaxValueValidator(Decimal('100'))]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_ac_i_max_a',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Micro-onduleur — courant AC maximal de sortie (A). Vide = non publié.', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_ac_kw',
            field=models.DecimalField(blank=True, decimal_places=3, help_text='Micro-onduleur — puissance AC nominale (kW ; trois décimales parce que ces fiches se publient en watts, ex. 0,365 kW). Vide = non publiée.', max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_ac_tension_v',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Micro-onduleur — tension AC nominale de sortie (V). Vide = non publiée.', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_ac_unites_max_par_branche',
            field=models.PositiveSmallIntegerField(blank=True, help_text="Micro-onduleur — nombre maximal d'unités admises sur une même branche AC. Vide = non publié.", null=True, validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_i_out_max_a',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Optimiseur — courant de sortie maximal (A). Vide = non publié.', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_modules_max_par_chaine',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Nombre maximal de modules équipés admis sur une même chaîne. Vide = non publié.', null=True, validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_pmax_out_w',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Optimiseur — puissance de sortie maximale (W). Vide = non publiée.', max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_v_out_max',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Optimiseur — tension de sortie maximale (V). Vide = non publiée.', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_v_out_min',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Optimiseur — tension de sortie minimale (V). Vide = non publiée.', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_v_out_nominal_v',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Optimiseur — tension de sortie NOMINALE (V). Vide = non publiée.', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='rendement_par_irradiance',
            field=models.JSONField(blank=True, help_text='Courbe de rendement à éclairement partiel publiée : [{"w_m2": 200, "rendement_relatif_pct": 97.5}, …] — le rendement RELATIF (% du rendement STC) à chaque niveau d\'irradiance. Vide = non publiée : l\'étape « niveau d\'irradiance » est omise en le disant.', null=True, validators=[apps.stock.models.valider_courbe_irradiance]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='tolerance_pmax_max_pct',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Tolérance de puissance Pmax publiée — borne HAUTE (%, ex. 3 pour un tri « 0/+3 % »). Vide = non publiée.', max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='tolerance_pmax_min_pct',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Tolérance de puissance Pmax publiée — borne BASSE (%, ex. 0 pour un tri « 0/+3 % », −3 pour « ±3 % »). Vide = non publiée.', max_digits=4, null=True),
        ),
    ]
