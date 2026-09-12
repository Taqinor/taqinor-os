"""NTJUR15 — bannière « reprendre la provision » à la clôture du dossier.

Deux drapeaux ADDITIFS (défaut ``False``, aucun dossier existant touché) :
``reprise_provision_proposee`` (levé par la clôture d'un dossier qui porte une
provision) et ``reprise_provision_traitee`` (posé par la décision — reprise ou
abandon explicite — pour que la bannière ne revienne pas à chaque
rechargement).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('juridique', '0004_ntjur14_provision_risque'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossierjuridique',
            name='reprise_provision_proposee',
            field=models.BooleanField(
                default=False,
                verbose_name='Reprise de provision proposée'),
        ),
        migrations.AddField(
            model_name='dossierjuridique',
            name='reprise_provision_traitee',
            field=models.BooleanField(
                default=False,
                verbose_name='Reprise de provision traitée'),
        ),
    ]
