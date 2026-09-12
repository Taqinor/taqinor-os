# NTHCM27 — genre déclaré (analytics diversité AGRÉGÉE uniquement).
#
# ADDITIF et SÛR : AddField à défaut vide — aucun dossier existant ne se voit
# attribuer un genre, il reste « non renseigné » et apparaît comme tel dans la
# répartition (jamais réparti d'office dans une catégorie inventée).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0101_nthcm24_taches_sortie_acteurs'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossieremploye',
            name='genre',
            field=models.CharField(
                blank=True,
                choices=[('femme', 'Femme'), ('homme', 'Homme'),
                         ('autre', 'Autre')],
                default='', max_length=6, verbose_name='Genre'),
        ),
    ]
