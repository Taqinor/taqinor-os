"""NTI18N35 — réglage "forcer la langue d'interface" par société (verrouillage).

Additif : défaut False = comportement historique inchangé (chaque
utilisateur choisit librement sa langue d'interface).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0093_companyprofile_langue_repli'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='langue_interface_verrouillee',
            field=models.BooleanField(
                default=False,
                help_text="Empêche les utilisateurs de la société de "
                          "changer de langue d'interface individuellement ; "
                          'impose la langue par défaut de la société '
                          '(langue_repli) à tous. Désactivé par défaut.',
                verbose_name="Langue d'interface verrouillée"),
        ),
    ]
