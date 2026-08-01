# Generated for EZ7 — « Signature client obligatoire pour clôturer ».
# Additif et réversible : un seul BooleanField, défaut False (comportement
# historique byte-identique — la signature reste facultative tant que le
# réglage n'est pas activé par la société).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0066_ntext18_gabaritdocumentcustom'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='signature_client_obligatoire',
            field=models.BooleanField(default=False, help_text="Exige la signature du client sur l'intervention avant de passer au statut « Terminée ». Désactivé par défaut : la signature reste possible mais facultative.", verbose_name='Signature client obligatoire pour clôturer'),
        ),
    ]
