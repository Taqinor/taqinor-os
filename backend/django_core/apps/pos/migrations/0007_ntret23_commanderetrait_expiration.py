# NTRET23 — Click & Collect (XPOS15) : expiration de réservation auto-libérée.
# Additif : NULL = pas de délai configuré, réservation qui n'expire jamais
# (comportement historique inchangé).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0006_ntret5_arrhes"),
    ]

    operations = [
        migrations.AddField(
            model_name="commanderetrait",
            name="date_expiration_reservation",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
