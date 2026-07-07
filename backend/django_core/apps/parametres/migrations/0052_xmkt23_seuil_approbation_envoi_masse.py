# XMKT23 - seuil d'approbation avant envoi de masse (defaut 100 = comportement
# de reference; le comportement HISTORIQUE reel restait sans blocage tant que
# XMKT23 n'existait pas cote compta — desormais applique via ce seuil).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0051_xmkt22_sunset_fenetre_jours"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="seuil_approbation_envoi_masse",
            field=models.PositiveIntegerField(
                default=100,
                help_text=(
                    "Au-delà de ce nombre de destinataires, l'envoi d'une "
                    "campagne exige l'approbation d'un Responsable/Directeur."),
            ),
        ),
    ]
