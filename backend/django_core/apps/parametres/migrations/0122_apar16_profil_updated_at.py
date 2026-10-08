"""APAR16 — ``CompanyProfile.updated_at`` : verrou optimiste du profil société.

ADDITIF : une colonne nullable (les profils existants restent NULL jusqu'à leur
prochaine écriture). Réversible : ``python manage.py migrate parametres 0121``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0121_ciq218_cgv_par_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='updated_at',
            field=models.DateTimeField(
                auto_now=True, null=True, verbose_name='Modifié le'),
        ),
    ]
