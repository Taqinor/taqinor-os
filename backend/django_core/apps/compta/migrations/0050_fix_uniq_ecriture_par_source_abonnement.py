"""Fix — exclut source_type='abonnement' de uniq_ecriture_par_source.

Un ``AbonnementEcriture`` (XACC8) génère UNE écriture PAR ÉCHÉANCE : le
``source_id`` (id de l'abonnement) reste le MÊME à chaque génération alors
que plusieurs écritures légitimes doivent coexister (une par mois/trimestre).
Le contrainte unique (company, source_type, source_id) bloquait la 2e
échéance d'un même abonnement (IntegrityError). L'idempotence pour ce type de
source est déjà assurée par ``reference`` (« AB{id}-{YYYY-MM} »), vérifiée
dans ``services.generer_ecritures_recurrentes`` avant toute création.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0049_prorata_tva_familles_non_deductibles'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='ecriturecomptable',
            name='uniq_ecriture_par_source',
        ),
        migrations.AddConstraint(
            model_name='ecriturecomptable',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('source_id__isnull', False),
                ) & ~models.Q(('source_type', 'abonnement')),
                fields=('company', 'source_type', 'source_id'),
                name='uniq_ecriture_par_source',
            ),
        ),
    ]
