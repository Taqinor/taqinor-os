# Hand-written migration (XSAL5 — lignes optionnelles sur devis).
# Additif & réversible : un seul nouveau champ booléen sur LigneDevis, défaut
# False. Une ligne optionnelle est proposée au client HORS totaux tant qu'elle
# n'est pas activée (bascule à False via le service activate_optional_line).
# Défaut False = comportement historique octet-identique quand aucune option
# n'est utilisée. Entièrement réversible.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0084_odx19_repoint_achats_crossapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignedevis',
            name='optionnelle',
            field=models.BooleanField(
                default=False,
                help_text='Ligne optionnelle (add-on) : proposée au client hors '
                          "total tant qu'elle n'est pas activée. Défaut False = "
                          'ligne normale.'),
        ),
    ]
