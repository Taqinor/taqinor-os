# Generated manually — XPAI4 13e mois & gratifications + runs hors-cycle.
#
# Additif : ``PeriodePaie.type_run`` (mensuel / hors_cycle) permettant un run
# indépendant du cycle mensuel (13e mois / prime de bilan), et
# ``BulletinPaie.TYPE_GRATIFICATION`` (nouveau choix, pas de champ ajouté).
# L'unicité de ``PeriodePaie`` est étendue pour inclure ``type_run`` : un run
# hors-cycle peut désormais coexister avec le run mensuel du même mois.

from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI4 — 13e mois & gratifications + runs hors-cycle."""

    dependencies = [
        ("paie", "0023_xpai3_mutuelle"),
    ]

    operations = [
        migrations.AddField(
            model_name="periodepaie",
            name="type_run",
            field=models.CharField(
                choices=[
                    ("mensuel", "Mensuel"),
                    ("hors_cycle", "Hors-cycle (prime/rappel)"),
                ],
                default="mensuel",
                max_length=12,
                verbose_name="Type de run",
            ),
        ),
        migrations.AlterField(
            model_name="bulletinpaie",
            name="type_bulletin",
            field=models.CharField(
                choices=[
                    ("normal", "Normal"),
                    ("rectificatif", "Rectificatif"),
                    ("rappel", "Rappel"),
                    ("stc", "Solde de tout compte"),
                    ("gratification", "13e mois / gratification"),
                ],
                default="normal",
                max_length=14,
                verbose_name="Nature du bulletin",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="periodepaie",
            unique_together={("company", "annee", "mois", "type_run")},
        ),
    ]
