"""NTSRV6 - Competences requises par categorie de ticket (additif, optionnel).

M2M string-FK vers `rh.Competence` : la table de liaison vit cote sav (aucune
ecriture dans les migrations de rh). Une categorie SANS competence definie
garde exactement le comportement actuel (aucun filtre d'affectation).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0014_competence_competenceemploye'),
        ('sav', '0054_ntsrv5_log_appel'),
    ]

    operations = [
        migrations.AddField(
            model_name='categorieticket',
            name='competences_requises',
            field=models.ManyToManyField(
                blank=True,
                help_text='Compétences exigées pour traiter un ticket de '
                          'cette catégorie (vide = aucune exigence, '
                          'comportement actuel).',
                related_name='categories_ticket_sav',
                to='rh.competence',
                verbose_name='Compétences requises',
            ),
        ),
        migrations.AddField(
            model_name='categorieticket',
            name='niveau_competence_min',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text='Niveau minimum attendu sur chaque compétence '
                          'requise (échelle rh.CompetenceEmploye : 0 non '
                          'acquis → 4 expert). Sans compétence requise, ce '
                          "niveau n'est jamais consulté.",
                verbose_name='Niveau minimum requis',
            ),
        ),
    ]
