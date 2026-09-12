"""NTJUR6 — référence LÂCHE vers le dossier juridique ouvert par escalade.

``PositiveIntegerField`` nullable (jamais une FK dure vers ``apps.juridique``)
— ADDITIF : aucune réclamation existante n'est touchée (NULL = jamais
escaladée).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('litiges', '0006_xfac21_type_recouvrement'),
    ]

    operations = [
        migrations.AddField(
            model_name='reclamation',
            name='dossier_juridique_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='ID du dossier juridique lié'),
        ),
    ]
