# Generated manually — PAIE25 provision pour congés payés (charge patronale).
#
# Additive et réversible. Ajoute le champ de snapshot
# ``BulletinPaie.provision_conges`` : engagement social mensuel constitué sur
# la base des jours de CP acquis dans le mois × le taux journalier du salarié.
# Charge employeur informative — jamais déduite du net du salarié.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE25 — Provision pour congés payés (charge patronale informative)."""

    dependencies = [
        ("paie", "0012_formation_professionnelle"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulletinpaie",
            name="provision_conges",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=14,
                verbose_name="Provision congés payés (patronal)",
            ),
        ),
    ]
