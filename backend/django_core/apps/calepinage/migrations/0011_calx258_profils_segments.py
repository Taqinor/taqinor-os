"""CALX258 — la famille ``pompage`` rejoint résidentiel/commercial/
industriel/agricole/autre.

ADDITIF, et SANS colonne neuve : ``famille`` reste le même ``CharField`` ;
seule la LISTE PYTHON de ses choix admis change (une contrainte de
validation, jamais une contrainte de base). La forme SEGMENTÉE de
``courbe`` (``{saison: {jour_type: [24]}}``, ``jour_type`` ∈ ``ouvre`` /
``weekend`` / ``ferie``) est elle aussi un choix de FORME côté application
(``ProfilTypeConsommation.clean()``, ``services/profils_types.py``) : le
``JSONField`` ``courbe`` ne change pas de schéma. Une société qui n'édite
rien continue de lire EXACTEMENT les mêmes profils qu'avant (forme plate
préservée à l'identique).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0010_calx145_parametres_simulation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profiltypeconsommation',
            name='famille',
            field=models.CharField(
                choices=[
                    ('residentiel', 'Résidentiel'),
                    ('commercial', 'Commercial / tertiaire'),
                    ('industriel', 'Industriel'),
                    ('agricole', 'Agricole'),
                    ('pompage', 'Pompage'),
                    ('autre', 'Autre'),
                ],
                default='residentiel', max_length=16,
                verbose_name='Famille'),
        ),
    ]
