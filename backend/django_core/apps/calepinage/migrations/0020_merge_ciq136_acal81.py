"""Fusion des deux feuilles calepinage : vague 1 (CIQ112 → CIQ136) et main
(ACAL33 → ACAL40 → ACAL81). Opérations indépendantes (choix de
``SystemeFixation.mode_pose`` + ``Calepinage.contraintes_site`` d'un côté ;
contrainte un-par-devis, recalcul d'empreinte, ``Calepinage.systeme_fixation``
de l'autre) : aucune opération ici."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0018_ciq136_contraintes_site'),
        ('calepinage', '0019_acal81_systeme_fixation_choisi'),
    ]

    operations = []
