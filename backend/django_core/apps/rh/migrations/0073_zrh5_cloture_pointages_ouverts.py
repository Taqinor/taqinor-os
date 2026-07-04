# Generated manually — ZRH5 clôture automatique des pointages oubliés.
# Additif.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH5 — Pointage.depart_auto + ReglageRH.pointage_auto_depart_apres_h
    (additif)."""

    dependencies = [
        ("rh", "0072_zrh4_jour_bloque_conge"),
    ]

    operations = [
        migrations.AddField(
            model_name="pointage",
            name="depart_auto",
            field=models.BooleanField(
                default=False, verbose_name="Départ clôturé automatiquement"),
        ),
        migrations.AddField(
            model_name="reglagerh",
            name="pointage_auto_depart_apres_h",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Clôture auto pointage après (heures)"),
        ),
    ]
