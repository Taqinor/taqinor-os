# XKB12 — Gabarits d'articles utilisateur : ``est_gabarit`` (défaut False —
# RÉTRO-COMPATIBLE, aucun article existant ne devient gabarit malgré lui).
# Entièrement additive, réversible par ``git revert`` / ``migrate kb 0011``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kb", "0011_kbarticlelien_type_cible_article"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbarticle",
            name="est_gabarit",
            field=models.BooleanField(default=False, verbose_name="Gabarit"),
        ),
    ]
