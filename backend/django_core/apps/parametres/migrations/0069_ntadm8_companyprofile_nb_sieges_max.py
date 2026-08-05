# NTADM8 — CompanyProfile.nb_sieges_max : quota de sièges (comptes actifs).
# NULL (défaut) = illimité, comportement actuel byte-identique. Jamais
# bloquant (voir authentication.services.sieges_utilises).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0068_ntadm7_companyprofile_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='nb_sieges_max',
            field=models.PositiveIntegerField(blank=True, help_text='Quota de sièges (comptes actifs) inclus dans la licence. Vide = illimité (défaut). Le dépassement alerte mais ne bloque jamais la création d\'un compte.', null=True, verbose_name='Nombre de sièges maximum'),
        ),
    ]
