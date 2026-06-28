"""FG88 — Date de tournée planifiée pour les visites préventives groupées.

Additif + réversible. Champ nullable/blank (pas de default) — aucune base
peuplée n'est affectée : les tickets existants restent sans date de tournée
jusqu'à ce qu'une tournée soit planifiée via l'action dédiée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0009_fg86_ticket_share_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="date_tournee",
            field=models.DateField(blank=True, null=True),
        ),
    ]
