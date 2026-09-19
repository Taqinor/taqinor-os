"""NTI18N22 — décomposition optionnelle de l'adresse libre en champs
structurés, additive.

`adresse` (TextField historique) reste inchangé — ces quatre champs sont de
nouvelles colonnes optionnelles, vides par défaut, sans migration de donnée :
une société existante n'est affectée en rien.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0090_companyprofile_nti18n20_es_prep'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='adresse_rue',
            field=models.CharField(
                blank=True, default='', max_length=255,
                help_text="Numéro et voie. Vide = utiliser l'adresse libre "
                          "(`adresse`) telle quelle.",
                verbose_name='Rue'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='adresse_code_postal',
            field=models.CharField(
                blank=True, default='', max_length=20,
                verbose_name='Code postal'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='adresse_ville',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name='Ville'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='adresse_pays',
            field=models.CharField(
                blank=True, default='', max_length=2,
                help_text='Code pays ISO 3166-1 alpha-2 de CETTE adresse '
                          '(ex. MA, FR, ES) — distinct de la langue/du '
                          'pack pays de la société.',
                verbose_name='Pays (adresse)'),
        ),
    ]
