# LITIGE4 — Liens lâches (par id) d'un litige qualité vers la non-conformité
# (NCR) et l'audit fin de chantier QHSE (additif, nullable, aucune contrainte
# cross-app : référence lâche par id, jamais un FK fort vers apps.qhse).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("litiges", "0003_litige3_bloque_relances"),
    ]

    operations = [
        migrations.AddField(
            model_name="reclamation",
            name="ncr_id",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="ID de la non-conformité QHSE (NCR)",
            ),
        ),
        migrations.AddField(
            model_name="reclamation",
            name="audit_id",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="ID de l'audit fin de chantier QHSE",
            ),
        ),
    ]
