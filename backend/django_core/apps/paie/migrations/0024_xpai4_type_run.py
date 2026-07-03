# Generated manually — XPAI4 13e mois & runs hors-cycle.
#
# Additif : ajoute PeriodePaie.type_run (mensuel/hors_cycle, défaut mensuel —
# comportement historique inchangé) et élargit l'unicité (company, annee,
# mois) -> (company, annee, mois, type_run) pour permettre un run hors-cycle
# sur le même mois qu'un run mensuel.

from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI4 — 13e mois & runs hors-cycle."""

    dependencies = [
        ("paie", "0023_xpai3_mutuelle"),
    ]

    operations = [
        migrations.AddField(
            model_name="periodepaie",
            name="type_run",
            field=models.CharField(
                choices=[("mensuel", "Mensuel"), ("hors_cycle", "Hors-cycle")],
                default="mensuel", max_length=12, verbose_name="Nature du run"),
        ),
        migrations.AlterUniqueTogether(
            name="periodepaie",
            unique_together={("company", "annee", "mois", "type_run")},
        ),
    ]
