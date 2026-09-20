"""CAL112 — facteur de bifacialité publié (remplace/complète le booléen).

``bifacial`` (booléen) ne dit QUE « bifacial ou non » : impossible d'en
tirer un gain face arrière. PVsyst modélise un facteur de bifacialité publié
par le fabricant combiné à un albédo de site (l'albédo se saisit côté projet
de calepinage — hors fiche produit, tâche séparée). Le booléen reste, non
supprimé.

ADDITIF PUR (``null=True``/``blank=True``) : aucune fiche existante n'est
modifiée. Vide = « non publié » ⇒ AUCUN gain bifacial calculé — jamais 0,
qui affirmerait à tort une bifacialité nulle mesurée.

RÉVERSIBLE : oui — un ``AddField`` d'une colonne NULL se défait par un
``RemoveField`` automatique, sans perte.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0149_cal111_fiche_modele_thermique'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bifacialite_pct',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text='Facteur de bifacialité publié par le fabricant '
                          '(%). Vide = non publié : aucun gain bifacial '
                          'calculé.',
                max_digits=4, null=True),
        ),
    ]
