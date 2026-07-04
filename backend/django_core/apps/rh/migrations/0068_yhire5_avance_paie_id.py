# Generated manually — YHIRE5 lien AvanceSalaire (rh) -> AvanceSalarie
# (paie) : champ additif d'idempotence, aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):
    """YHIRE5 — AvanceSalaire.paie_avance_id (additif)."""

    dependencies = [
        ("rh", "0067_quiz_formation"),
    ]

    operations = [
        migrations.AddField(
            model_name="avancesalaire",
            name="paie_avance_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Avance paie liée (retenue)"),
        ),
    ]
