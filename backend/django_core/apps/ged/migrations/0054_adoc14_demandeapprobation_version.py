"""ADOC14 — version relue par une demande d'approbation (FK nullable, additive).

Posée côté serveur à la création de la demande (dernière version du document).
SET_NULL : supprimer une version ne supprime jamais la trace de la demande.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0053_adoc68_demande_version_signee'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeapprobation',
            name='version',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandes_approbation',
                to='ged.documentversion', verbose_name='version relue'),
        ),
    ]
