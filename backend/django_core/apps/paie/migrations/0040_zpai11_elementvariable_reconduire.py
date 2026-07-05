# Generated manually — ZPAI11 ElementVariable.reconduire + reconduit_depuis :
# champs additifs (défaut False/NULL = comportement historique inchangé,
# aucun élément existant reconduit rétroactivement). ``reconduit_depuis`` +
# la contrainte (periode, reconduit_depuis) portent l'idempotence de la
# reconduction. Aucune donnée existante touchée.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZPAI11 — ElementVariable.reconduire/reconduit_depuis (additif)."""

    dependencies = [
        ("paie", "0039_zpai9_type_entree_ponctuelle"),
    ]

    operations = [
        migrations.AddField(
            model_name="elementvariable",
            name="reconduire",
            field=models.BooleanField(
                default=False,
                verbose_name="Reconduire vers la période suivante"),
        ),
        migrations.AddField(
            model_name="elementvariable",
            name="reconduit_depuis",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reconductions", to="paie.elementvariable",
                verbose_name="Reconduit depuis (élément M-1)"),
        ),
        migrations.AlterUniqueTogether(
            name="elementvariable",
            unique_together={("periode", "reconduit_depuis")},
        ),
    ]
