"""CKP2 — l'ancre de cadence, pour la matérialisation RÉACTIVE.

``RelanceEtape.cadence_depart`` est l'instant de DÉPART depuis lequel le
gabarit date toutes ses touches. Il devient nécessaire le jour où la cadence
cesse d'être matérialisée d'un bloc : la touche J+5, créée seulement quand la
touche J+3 est close, doit tomber exactement où l'aperçu (MRY30) l'avait
annoncée — donc être datée depuis le MÊME départ, pas depuis l'instant de
clôture.

ADDITIVE et NULLABLE : aucun défaut à backfiller sur une table peuplée, aucune
contrainte posée (YDATA20 sans les trois temps). Les lignes existantes gardent
NULL — c'est la vérité (elles n'ont jamais porté cette ancre) et le service
retombe alors sur la plus ancienne échéance de leur cadence.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0097_ckp1_relanceetape_annulee'),
    ]

    operations = [
        migrations.AddField(
            model_name='relanceetape',
            name='cadence_depart',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Départ de la cadence'),
        ),
    ]
