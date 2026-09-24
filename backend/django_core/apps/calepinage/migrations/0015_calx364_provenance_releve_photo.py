"""CALX364 — la PROVENANCE d'une donnée de terrain, et la reprise d'une visite.

ADDITIVE et SANS RÉÉCRITURE : ``provenance`` naît à ``'saisie'`` pour tout
l'existant (D12 — un relevé ou une photo déposés avant cette migration ONT été
saisis dans le module), ``slot_code`` vide, ``visite_id`` nul et ``mesures``
vide. Aucune ligne n'est touchée par un ``RunPython``.

``ReleveTerrain`` n'avait aucun champ pour des mesures LIBRES (une longueur,
une pente, une orientation) : ses ``chaines`` sont des chaînes de cotes à
fermer. Les convertir serait inventer une géométrie (D7) — les mesures reprises
vivent donc dans leur propre colonne ``mesures``, telles que saisies.

La contrainte partielle ``(calepinage, visite_id)`` ne porte que sur les
relevés REPRIS (``visite_id`` non nul) : aucune ligne existante n'y entre.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0014_calx358_systeme_fixation'),
    ]

    operations = [
        migrations.AddField(
            model_name='photosite',
            name='provenance',
            field=models.CharField(
                choices=[('saisie', 'Saisie dans le calepinage'),
                         ('visite', 'Reprise de la visite technique')],
                default='saisie', max_length=10, verbose_name='Provenance'),
        ),
        migrations.AddField(
            model_name='photosite',
            name='slot_code',
            field=models.CharField(blank=True, default='', max_length=80,
                                   verbose_name='Emplacement de visite'),
        ),
        migrations.AddField(
            model_name='releveterrain',
            name='provenance',
            field=models.CharField(
                choices=[('saisie', 'Saisie dans le calepinage'),
                         ('visite', 'Reprise de la visite technique')],
                default='saisie', max_length=10, verbose_name='Provenance'),
        ),
        migrations.AddField(
            model_name='releveterrain',
            name='visite_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Visite reprise (identifiant)'),
        ),
        migrations.AddField(
            model_name='releveterrain',
            name='mesures',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Mesures reprises (telles que saisies)'),
        ),
        migrations.AddConstraint(
            model_name='releveterrain',
            constraint=models.UniqueConstraint(
                condition=models.Q(visite_id__isnull=False),
                fields=('calepinage', 'visite_id'),
                name='uniq_releve_reprise_par_visite'),
        ),
    ]
