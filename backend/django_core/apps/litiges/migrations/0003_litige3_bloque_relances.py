# LITIGE3 — Ajout du champ bloque_relances sur Reclamation (additif).
# Default True : les litiges existants bloquent les relances par défaut,
# comportement conservatif (aucune relance envoyée par erreur).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("litiges", "0002_reclamationactivity"),
    ]

    operations = [
        migrations.AddField(
            model_name="reclamation",
            name="bloque_relances",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Si coché, suspend les relances automatiques sur la facture "
                    "liée tant que ce litige est ouvert."
                ),
                verbose_name="Bloque les relances",
            ),
        ),
    ]
