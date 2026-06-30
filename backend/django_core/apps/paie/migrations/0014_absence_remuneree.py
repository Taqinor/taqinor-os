# Generated manually — PAIE26 paiement & décompte des congés/absences.
#
# Additive et réversible. Ajoute deux drapeaux sur ``ElementVariable`` (utilisés
# uniquement pour les éléments ``TYPE_ABSENCE``) :
# * ``remunere`` (défaut False) : une absence rémunérée (congé payé) n'est ni
#   déduite du salaire de base proraté, ni portée en retenue.
# * ``deduit_solde`` (défaut False) : reprend la règle RH du décompte du compteur
#   de congés (informatif côté paie).
# Défauts conservateurs (False) : le comportement historique des absences (toutes
# décomptées) reste inchangé tant que les drapeaux ne sont pas posés.

from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE26 — Absence rémunérée / décompte du solde sur l'élément variable."""

    dependencies = [
        ("paie", "0013_provision_conges"),
    ]

    operations = [
        migrations.AddField(
            model_name="elementvariable",
            name="remunere",
            field=models.BooleanField(
                default=False, verbose_name="Absence rémunérée"),
        ),
        migrations.AddField(
            model_name="elementvariable",
            name="deduit_solde",
            field=models.BooleanField(
                default=False, verbose_name="Déduit du solde de congés"),
        ),
    ]
