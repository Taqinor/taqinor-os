# XFAC8 — Canal par niveau de relance (email / WhatsApp / courrier / appel).
# Additif : un champ avec défaut 'email' → comportement historique inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0051_xfac6_penalites_relance"),
    ]

    operations = [
        migrations.AddField(
            model_name="followuplevel",
            name="canal",
            field=models.CharField(
                choices=[
                    ("email", "Email"),
                    ("whatsapp", "WhatsApp"),
                    ("courrier", "Courrier"),
                    ("appel", "Appel (tâche téléphonique)"),
                ],
                default="email", max_length=10),
        ),
        migrations.AddField(
            model_name="relancelog",
            name="canal",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="relancelog",
            name="courrier_pdf_key",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
