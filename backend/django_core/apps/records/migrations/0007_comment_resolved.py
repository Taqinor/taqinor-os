# XKB13 — Résolution de fil sur les commentaires génériques (``records.Comment``).
# ``resolved`` (défaut False — RÉTRO-COMPATIBLE, tous les commentaires existants
# restent non résolus). Introduit pour les commentaires d'article KB mais
# générique/réutilisable (Comment sert déjà tous les modèles ALLOWED_TARGETS).
# Entièrement additive, réversible par ``git revert`` / ``migrate records 0006``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0006_remove_tag_records_tag_company_nom_uniq_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="resolved",
            field=models.BooleanField(default=False, verbose_name="Résolu"),
        ),
    ]
