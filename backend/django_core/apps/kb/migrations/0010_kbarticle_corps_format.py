# XKB10 — Éditeur Markdown : ``corps_format`` (texte/markdown) sur KbArticle.
# Défaut ``texte`` — RÉTRO-COMPATIBLE, aucun rendu Markdown des articles
# existants. Le rendu/sanitizing Markdown vit entièrement côté frontend ; ce
# champ ne fait que porter le choix de format. Entièrement additive,
# réversible par ``git revert`` / ``migrate kb 0009``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kb", "0009_kbarticle_visibilite_acl_utilisateur"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbarticle",
            name="corps_format",
            field=models.CharField(
                choices=[("texte", "Texte brut"), ("markdown", "Markdown")],
                default="texte",
                max_length=10,
                verbose_name="Format du contenu",
            ),
        ),
    ]
