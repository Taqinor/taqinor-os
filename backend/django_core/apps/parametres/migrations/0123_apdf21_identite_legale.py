"""APDF21 — identité légale du profil société : capital social + forme juridique.

ADDITIF : deux colonnes texte, défaut '' (les profils existants restent vides).
Réversible : ``python manage.py migrate parametres 0122``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0122_apar16_profil_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='capital_social',
            field=models.CharField(
                blank=True, default='', max_length=60,
                help_text="Capital social tel qu'imprimé (ex. 100 000,00 MAD)."),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='forme_juridique',
            field=models.CharField(
                blank=True, default='', max_length=60,
                help_text='Forme juridique (ex. SARLAU, SARL, SA).'),
        ),
    ]
