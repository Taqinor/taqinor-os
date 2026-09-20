"""NTI18N20 — Pack pays Espagne, préparation de champs (squelette, non actif).

Additif : trois champs texte optionnels, tous vides par défaut. Aucune
société existante n'est affectée ; aucune validation ni activation
commerciale n'est branchée par cette migration (GATED-founder avant toute
vente commerciale en Espagne).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0089_messagetemplate_cles_visite'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='nif_cif',
            field=models.CharField(
                blank=True, default='', max_length=20,
                help_text='Identifiant fiscal espagnol (NIF personne '
                          'physique, CIF personne morale). Préparation '
                          'pack pays ES — inactif.',
                verbose_name='NIF/CIF'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='adresse_provincia',
            field=models.CharField(
                blank=True, default='', max_length=100,
                help_text='Province espagnole. Préparation pack pays ES '
                          '— inactif.',
                verbose_name='Provincia (ES)'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='adresse_comunidad_autonoma',
            field=models.CharField(
                blank=True, default='', max_length=100,
                help_text='Communauté autonome espagnole. Préparation '
                          'pack pays ES — inactif.',
                verbose_name='Comunidad autónoma (ES)'),
        ),
    ]
