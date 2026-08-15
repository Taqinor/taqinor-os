# NTAI22 — Analyse du transcript (objections / next-steps / sentiment).
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur `0001_initial` de cette app.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conversation_ai', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='appelcommercial',
            name='analyse_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='appelcommercial',
            name='analyse_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='appelcommercial',
            name='sentiment',
            field=models.CharField(blank=True, default='', help_text="Sentiment global déduit du transcript (positif/neutre/negatif) — vide tant que l'appel n'est pas analysé.", max_length=10),
        ),
    ]
