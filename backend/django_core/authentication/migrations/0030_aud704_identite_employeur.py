"""AUD704 — identité employeur sur ``Company`` (mentions du bulletin de paie).

Additive et réversible : cinq colonnes de texte, toutes vides par défaut.
Aucune société existante n'est modifiée ; le gabarit du bulletin n'imprime que
les mentions réellement renseignées.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0029_sol8_company_pays'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='adresse',
            field=models.TextField(
                blank=True, default='',
                help_text='Adresse du siège, imprimée en en-tête du bulletin '
                          'de paie.',
                verbose_name='Adresse'),
        ),
        migrations.AddField(
            model_name='company',
            name='registre_commerce',
            field=models.CharField(
                blank=True, default='', max_length=50,
                verbose_name='Registre du commerce (RC)'),
        ),
        migrations.AddField(
            model_name='company',
            name='identifiant_fiscal',
            field=models.CharField(
                blank=True, default='', max_length=50,
                verbose_name='Identifiant fiscal (IF)'),
        ),
        migrations.AddField(
            model_name='company',
            name='ice',
            field=models.CharField(
                blank=True, default='', max_length=50,
                help_text="Identifiant Commun de l'Entreprise.",
                verbose_name='ICE'),
        ),
        migrations.AddField(
            model_name='company',
            name='numero_cnss_employeur',
            field=models.CharField(
                blank=True, default='', max_length=50,
                verbose_name="N° d'affiliation CNSS employeur"),
        ),
    ]
