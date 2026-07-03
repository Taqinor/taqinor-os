# XKB8 — Arborescence d'articles (pages imbriquées) : ``parent`` self-FK
# nullable (NULL = racine) + ``ordre`` entier pour le réordonnancement manuel
# parmi les frères. Entièrement additive (deux nouvelles colonnes + un index),
# réversible par ``git revert`` / ``migrate kb 0007``. Anti-cycle validé côté
# service, jamais en base (une contrainte SQL récursive serait fragile).
# Index nommé EXPLICITEMENT (≤30 car.) pour éviter toute divergence avec le
# nom haché déterministe de Django.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kb", "0007_kblectureobligatoire"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbarticle",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="enfants",
                to="kb.kbarticle",
                verbose_name="Article parent",
            ),
        ),
        migrations.AddField(
            model_name="kbarticle",
            name="ordre",
            field=models.PositiveIntegerField(default=0, verbose_name="Ordre"),
        ),
        migrations.AddIndex(
            model_name="kbarticle",
            index=models.Index(
                fields=["company", "parent", "ordre"],
                name="kb_article_parent_ordre_idx",
            ),
        ),
    ]
