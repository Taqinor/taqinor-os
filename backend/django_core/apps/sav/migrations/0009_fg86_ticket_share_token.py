"""FG86 — Jeton de partage public pour les tickets SAV.

Additif + réversible. Le champ est nullable/blank (pas de default unique pour
toutes les lignes) afin d'éviter toute violation d'unicité sur une base peuplée.
Le jeton est généré lazily via Ticket.ensure_share_token().
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0008_merge_20260621_0546"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="share_token",
            field=models.CharField(
                blank=True,
                editable=False,
                help_text="Jeton public du lien client (FG86). Généré via ensure_share_token().",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
