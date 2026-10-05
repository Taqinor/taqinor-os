"""CIQ101 — champs C&I sur ``Produit`` et ``FicheTechnique``.

ADDITIF PUR (contrat ``contract_samples/produit_ci.json``) : trois colonnes
``Produit`` (``role_ci``, ``type_pose`` à chaîne vide ; ``delai_appro_jours``
NULL) et les champs de fiche ``ond_*`` ajoutés, ``lim_*``, ``log_*``,
``prot_*``, ``cable_*``, ``struct_*`` (chaîne vide, liste vide, objet vide ou
NULL = « non publié »). Cinq nouveaux choix de ``type_fiche`` ; aucune fiche
existante ne change de type, aucune donnée n'est réécrite.
RÉVERSIBLE : chaque ``AddField`` se défait par ``RemoveField`` (colonnes
neuves) et l'``AlterField`` des choix revient à la liste d'AGR101.
"""
from django.db import migrations, models


ROLES_CI = [
    'onduleur_string_tri', 'compteur_injection', 'controleur_injection',
    'logger_supervision', 'structure_ci', 'cable_ac', 'protection_ac',
    'protection_dc', 'coffret_ac', 'coffret_dc', 'mise_a_la_terre',
    'cellule_mt', 'etudes_ingenierie', 'pose_structure', 'pose_modules',
    'raccordement_ac', 'mise_en_service', 'dossier_raccordement',
    'levage_acces', 'transport_ci', 'om_ci', 'batterie_ci',
]
TYPES_POSE = ['toiture_inclinee', 'bac_acier', 'toit_plat_leste',
              'toit_plat_fixe', 'ombriere', 'sol']


def _choix(valeurs):
    return [(v, v) for v in valeurs]


def _texte(max_length, valeurs, aide):
    return models.CharField(blank=True, choices=_choix(valeurs), default='',
                            help_text=aide, max_length=max_length)


def _flottant(aide):
    return models.FloatField(blank=True, help_text=aide, null=True)


def _entier(aide):
    return models.PositiveSmallIntegerField(blank=True, help_text=aide,
                                            null=True)


def _liste(aide):
    return models.JSONField(blank=True, default=list, help_text=aide)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0162_agr104_roles_pompage'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='role_ci',
            field=models.CharField(
                blank=True, choices=_choix(ROLES_CI), db_index=True,
                default='',
                help_text="Rôle DÉCLARÉ dans une composition commerciale/"
                          "industrielle (compteur_injection, structure_ci…). "
                          "Vide = non déclaré.",
                max_length=32, verbose_name='Rôle C&I'),
        ),
        migrations.AddField(
            model_name='produit',
            name='type_pose',
            field=_texte(24, TYPES_POSE,
                         "Structures et prestations de pose seulement. Vide = "
                         "non publié : la structure n'est jamais choisie pour "
                         "un toit."),
        ),
        migrations.AddField(
            model_name='produit',
            name='delai_appro_jours',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text="Article « sur commande » : délai "
                          "d'approvisionnement (jours). null = tenu en stock "
                          "ou non saisi — jamais supposé."),
        ),
        # ── Onduleur (additifs, hors verrou PVOND)
        migrations.AddField(
            model_name='fichetechnique', name='ond_limitation_export',
            field=_texte(24, ['integree', 'compteur_requis',
                              'controleur_requis', 'non_publiee'],
                         "Onduleur — limitation d'export (vide = non "
                         "publié)."),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='ond_compteurs_compatibles',
            field=_liste('Onduleur — modèles de compteur compatibles '
                         'publiés.'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='ond_relais_decouplage',
            field=_texte(16, ['integre', 'externe', 'non_publie'],
                         'Onduleur — relais de découplage (vide = non '
                         'publié).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='ond_cos_phi_min',
            field=_flottant('Onduleur — facteur de puissance réglable mini '
                            '(valeur absolue).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='ond_cos_phi_max',
            field=_flottant('Onduleur — facteur de puissance réglable maxi.'),
        ),
        # ── Limiteur / compteur d'injection
        migrations.AddField(
            model_name='fichetechnique', name='lim_mode',
            field=_texte(24, ['compteur_direct', 'compteur_tc', 'controleur'],
                         'Limiteur — mode de raccordement (vide = non '
                         'publié).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='lim_i_max_a',
            field=_flottant('Limiteur — courant maxi mesuré en direct (A).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='lim_onduleurs_max',
            field=_entier("Limiteur — nombre d'onduleurs pilotés (vide = non "
                          "publié, jamais supposé)."),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='lim_marques',
            field=_liste("Limiteur — marques d'onduleur compatibles."),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='lim_phases',
            field=_entier('Limiteur — 1 ou 3 phases.'),
        ),
        # ── Logger
        migrations.AddField(
            model_name='fichetechnique', name='log_onduleurs_max',
            field=_entier("Logger — nombre d'onduleurs supervisés."),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='log_marques',
            field=_liste('Logger — marques supervisées.'),
        ),
        # ── Protection
        migrations.AddField(
            model_name='fichetechnique', name='prot_type',
            field=_texte(16, ['disjoncteur', 'sectionneur', 'fusible',
                              'parafoudre', 'ddr', 'interrupteur'],
                         'Protection — type (vide = non publié).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='prot_cote',
            field=_texte(4, ['ac', 'dc'], 'Protection — côté ac ou dc.'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='prot_calibre_a',
            field=_flottant('Protection — calibre (A).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='prot_pouvoir_coupure_ka',
            field=_flottant('Protection — pouvoir de coupure (kA).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='prot_poles',
            field=_entier('Protection — nombre de pôles.'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='prot_tension_v',
            field=_flottant('Protection — tension assignée (V).'),
        ),
        # ── Câble
        migrations.AddField(
            model_name='fichetechnique', name='cable_cote',
            field=_texte(4, ['ac', 'dc'], 'Câble — côté ac ou dc.'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='cable_section_mm2',
            field=_flottant('Câble — section (mm²).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='cable_ame',
            field=_texte(4, ['cu', 'al'],
                         'Câble — âme cu ou al (vide = non publié).'),
        ),
        # ── Structure
        migrations.AddField(
            model_name='fichetechnique', name='struct_type_pose',
            field=_texte(24, TYPES_POSE,
                         'Structure — type de pose (vocabulaire de '
                         'Produit.type_pose).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='struct_masse_kg_m2',
            field=_flottant('Structure — masse du système POSÉ (kg/m²), '
                            'notice fabricant.'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='struct_notice',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='Provenance de la masse : {"document": "", "date": '
                          'null, "page": null}.'),
        ),
        migrations.AlterField(
            model_name='fichetechnique',
            name='type_fiche',
            field=models.CharField(
                blank=True,
                choices=[
                    ('module', 'Module (panneau)'), ('onduleur', 'Onduleur'),
                    ('batterie', 'Batterie'),
                    ('optimiseur', 'Optimiseur / micro-onduleur'),
                    ('pompe', 'Pompe'),
                    ('variateur_pompage', 'Variateur de pompage'),
                    ('limiteur', "Compteur / limiteur d'injection"),
                    ('logger', 'Logger de supervision'),
                    ('protection', 'Protection'), ('cable', 'Câble'),
                    ('structure', 'Structure'), ('autre', 'Autre')],
                default='',
                help_text='Type de fiche technique (détermine les champs '
                          'applicables).',
                max_length=24),
        ),
    ]
