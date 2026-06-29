# GED17 — Cycle de vie documentaire (statut LOCAL à la GED).
#
# Ajoute un champ `statut` sur Document (machine à états
# brouillon→revue→approuvé→archivé→obsolète), gardée côté serveur par
# `services.change_lifecycle_status`. Additive et réversible : tous les
# documents existants reçoivent le défaut « brouillon ». Distinct du funnel
# STAGES.py (rule #2) — aucune importation de STAGES.py.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ged", "0010_documentchunk"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="statut",
            field=models.CharField(
                choices=[
                    ("brouillon", "Brouillon"),
                    ("revue", "En revue"),
                    ("approuve", "Approuvé"),
                    ("archive", "Archivé"),
                    ("obsolete", "Obsolète"),
                ],
                default="brouillon",
                max_length=12,
                verbose_name="statut du cycle de vie",
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["company", "statut"],
                name="ged_doc_co_statut_idx",
            ),
        ),
    ]
