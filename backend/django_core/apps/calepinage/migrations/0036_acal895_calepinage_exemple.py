# ACAL895 (D-ACAL-42) — le drapeau « exemple » d'un calepinage (SCHEMA).
#
# Migration ADDITIVE et réversible : une colonne booléenne fausse par défaut
# (aucune ligne réécrite) et la contrainte lead-ou-client élargie à « ou
# exemple ». Aucune donnée posée : les exemples ne naissent que de la commande
# ``semer_exemples_calepinage --apply``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0035_acal400_brouillon_serveur'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='exemple',
            field=models.BooleanField(default=False, verbose_name='Exemple'),
        ),
        migrations.RemoveConstraint(
            model_name='calepinage',
            name='calepinage_lead_ou_client',
        ),
        migrations.AddConstraint(
            model_name='calepinage',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ('lead_id__isnull', False), ('client__isnull', False),
                    ('exemple', True), _connector='OR'),
                name='calepinage_lead_ou_client'),
        ),
    ]
