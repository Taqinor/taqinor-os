"""CAL116 — type de fiche « optimiseur / micro-onduleur ».

``FicheTechnique.TypeFiche`` n'offrait que module/onduleur/batterie/autre ;
``grep -n "optimiseur" apps/ventes`` ne rend que
``composition_deux_optimiseurs`` (un comparateur de DIMENSIONNEMENT, sans
rapport avec un optimiseur de puissance). PVsyst modélise les optimiseurs
comme composants avec leur propre perte de conversion, PV*SOL les
micro-onduleurs.

ADDITIF PUR : le nouveau choix ``'optimiseur'`` et six champs optionnels
(``null=True``/``blank=True``) — aucune fiche existante n'est modifiée, la
migration ne change le ``type_fiche`` d'aucune ligne.

RÉVERSIBLE : oui — le choix de ``TypeFiche`` s'ajoute sans migration de
données, et les six ``AddField`` de colonnes NULL se défont par un
``RemoveField`` automatique, sans perte.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0152_cal115_fiche_onduleur_mppt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fichetechnique',
            name='type_fiche',
            field=models.CharField(
                blank=True,
                choices=[
                    ('module', 'Module (panneau)'),
                    ('onduleur', 'Onduleur'),
                    ('batterie', 'Batterie'),
                    ('optimiseur', 'Optimiseur / micro-onduleur'),
                    ('autre', 'Autre'),
                ],
                default='',
                help_text='Type de fiche technique (détermine les champs '
                          'applicables).',
                max_length=16),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_pmax_in_w',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text="Puissance d'entrée max. de l'optimiseur (Wc). "
                          'Vide = non publié.',
                max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_v_in_min',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text="Tension d'entrée minimale (V). Vide = non "
                          'publié.',
                max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_v_in_max',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text="Tension d'entrée maximale (V). Vide = non "
                          'publié.',
                max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_i_in_max_a',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text="Courant d'entrée maximal (A). Vide = non "
                          'publié.',
                max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_rendement_pct',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text='Rendement de conversion publié (%). Vide = '
                          'non publié.',
                max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_modules_par_optimiseur',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Nombre de modules gérés par optimiseur (1 ou '
                          '2, typiquement). Vide = non publié.',
                null=True),
        ),
    ]
