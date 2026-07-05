# ZGED11 — Propriétés d'article (champs personnalisés typés, réutilise
# `customfields`). Entièrement additif : ``proprietes`` défaut {} sur toutes
# les lignes existantes (comportement historique inchangé). Réversible par
# ``git revert`` / ``migrate kb 0020``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kb', '0020_kbarticle_emoji_couverture'),
    ]

    operations = [
        migrations.AddField(
            model_name='kbarticle',
            name='proprietes',
            field=models.JSONField(
                blank=True, default=dict, null=True,
                verbose_name='Propriétés'),
        ),
    ]
