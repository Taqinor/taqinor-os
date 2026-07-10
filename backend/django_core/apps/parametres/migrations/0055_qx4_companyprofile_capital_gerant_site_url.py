"""QX4 — identité société additive : capital, gérant, site_url.

Deux faits sans logement (capital social + nom du gérant) et l'URL du site
public, threadés dans le rendu du devis résidentiel pour dé-taqinoriser le
moteur (fuite multi-tenant). Additif/blank : une société existante garde une
sortie strictement identique tant que ces champs restent vides.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0054_companyprofile_arrondi_caisse'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='capital',
            field=models.CharField(
                blank=True, default='', max_length=60,
                help_text='Capital social (texte libre, ex. « 100 000,00 MAD ») '
                          'affiché dans la bande légale du devis.'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='gerant',
            field=models.CharField(
                blank=True, default='', max_length=120,
                help_text='Nom du gérant / représentant légal affiché dans la '
                          'bande légale du devis.'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='site_url',
            field=models.CharField(
                blank=True, default='', max_length=200,
                help_text='URL du site public (ex. « taqinor.ma ») — pilote les '
                          'liens produits/réalisations/garanties du devis.'),
        ),
    ]
