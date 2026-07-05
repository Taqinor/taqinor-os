# Generated manually — ZRH16 localisation de télétravail par jour de semaine.
# Additif, champ JSONField avec défaut vide.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH16 — DossierEmploye.localisation_hebdo (additif)."""

    dependencies = [
        ("rh", "0074_zrh7_modele_evaluation"),
    ]

    operations = [
        migrations.AddField(
            model_name="dossieremploye",
            name="localisation_hebdo",
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name="Localisation hebdomadaire"),
        ),
    ]
