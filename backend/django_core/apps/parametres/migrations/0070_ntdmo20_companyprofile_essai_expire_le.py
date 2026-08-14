# NTDMO20 — CompanyProfile.essai_expire_le : bannière d'expiration d'essai
# (fondation). NULL (défaut) = aucun changement pour toute société existante ;
# assignation réservée au founder (admin Django / Paramètres).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0069_ntadm8_companyprofile_nb_sieges_max'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='essai_expire_le',
            field=models.DateField(blank=True, help_text='Vide = aucun essai en cours (défaut). Renseignée et dépassée : une bannière non-bloquante « Votre essai a expiré » est affichée sur toutes les pages, sans jamais bloquer d\'action. Assignation réservée au founder.', null=True, verbose_name="Date d'expiration de l'essai"),
        ),
    ]
