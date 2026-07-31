# WIR94 — Route l'upload portail vers le stockage GED canonique.
#
# Ajoute ``DocumentClientPortail.document_ged`` (FK nullable vers
# ``ged.Document``, SET_NULL) : le fichier téléversé par le client est en plus
# déposé comme document GED réel (``ged.services.deposit_document``) et
# référencé ici — le ``FileField`` historique (``fichier``) reste inchangé
# pour compatibilité ascendante. Migration ADDITIVE (aucune donnée touchée).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0001_odx12_portail_split'),
        ('ged', '0043_zged15_backfill_document_reference'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentclientportail',
            name='document_ged',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='ged.document',
                verbose_name='Document GED',
            ),
        ),
    ]
