"""BATHOMO/F3 (revue adversariale 26/08/2026) — ``bat_max_modules_par_banc``
NE PEUT PAS valoir 0.

Le champ signifie « limite du nombre de modules identiques par banc,
``None`` = illimité » : 0 n'est pas une limite, c'est une banque IMPOSSIBLE
(``apps.ventes.services.composition_residentielle`` rejetterait TOUTE
candidate pour ce produit, y compris via un pin déjà engagé sur un devis —
un « avec batterie » qui part silencieusement sans aucune batterie). Le
formulaire produit (``ProduitForm.jsx``) postait pourtant ``min="0"`` et le
``PositiveIntegerField`` d'origine acceptait 0 sans broncher.

``MinValueValidator(1)`` ferme la porte au niveau MODÈLE (donc API ET
formulaire — DRF dérive sa validation du champ modèle) : un ``full_clean()``
ou une écriture DRF sur 0 lève désormais, plutôt que de produire un vivier
batterie vide en silence à la composition.

AUCUNE DONNÉE À MIGRER : le champ vient d'être introduit (migration 0132,
même session) et la seule valeur fondateur posée (200, sur le Dyness 5 kWh)
respecte déjà la contrainte — un ``AlterField`` pur, sans ``RunPython``.

RÉVERSIBLE : oui — retirer le validateur ne perd aucune donnée (une valeur
existante ≥ 1 reste valide sans lui).
"""
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0132_bathomo_max_modules_par_banc'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fichetechnique',
            name='bat_max_modules_par_banc',
            field=models.PositiveIntegerField(blank=True, help_text='Nombre MAXIMUM de modules identiques dans un même banc (limite ≥ 1). Vide = illimité.', null=True, validators=[MinValueValidator(1)]),
        ),
    ]
