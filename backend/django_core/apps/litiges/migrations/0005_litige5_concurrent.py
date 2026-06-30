# LITIGE5 — Capture du concurrent/motif sur deal perdu (étend FG242).
# Additif : nouvelles colonnes optionnelles sur Reclamation, aucune existante
# modifiée. Le lead perdu est référencé par source_type='lead'/source_id (string
# FK lâche), jamais un FK fort vers apps.crm. Noms d'index n/a (aucun index).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("litiges", "0004_litige4_qhse_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="reclamation",
            name="concurrent_nom",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Nom du concurrent qui a remporté l'affaire. "
                    "Vide si inconnu."
                ),
                max_length=200,
                verbose_name="Concurrent gagnant",
            ),
        ),
        migrations.AddField(
            model_name="reclamation",
            name="concurrent_prix",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Prix proposé par le concurrent. Vide si inconnu.",
                max_digits=14,
                null=True,
                verbose_name="Prix du concurrent",
            ),
        ),
        migrations.AddField(
            model_name="reclamation",
            name="concurrent_devise",
            field=models.CharField(
                blank=True,
                default="MAD",
                max_length=8,
                verbose_name="Devise du prix concurrent",
            ),
        ),
        migrations.AddField(
            model_name="reclamation",
            name="motif_perte",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Raison pour laquelle le deal a été perdu (texte libre)."
                ),
                max_length=255,
                verbose_name="Motif de la perte",
            ),
        ),
    ]
