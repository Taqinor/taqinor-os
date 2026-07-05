# ZMKT12 - partage d'enquete par lien/email/QR : description d'accueil +
# message de fin. Additif : chaines vides par defaut = comportement actuel
# (aucun texte d'accueil/fin affiche).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0098_zmkt11_enquete_mode_acces"),
    ]

    operations = [
        migrations.AddField(
            model_name="enquete",
            name="description_accueil",
            field=models.TextField(
                blank=True, default="",
                verbose_name="Description d'accueil (avant de commencer)"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="message_fin",
            field=models.TextField(
                blank=True, default="",
                verbose_name="Message de fin (complétion)"),
        ),
    ]
