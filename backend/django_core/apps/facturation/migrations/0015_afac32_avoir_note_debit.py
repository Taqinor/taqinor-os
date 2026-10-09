"""AFAC32 (D-AFAC-C4) — ``Avoir.note_debit`` : l'avoir qui annule une note
de débit émise (« avoir de note de débit »).

ADDITIF : une clé étrangère nullable, aucun avoir existant modifié.
Réversible : revenir à facturation 0014.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0014_atot6_avoir_ventilation_tva'),
        ('ventes', '0135_merge_adev33_atot12'),
    ]

    operations = [
        migrations.AddField(
            model_name='avoir',
            name='note_debit',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='avoirs_annulation', to='ventes.notedebit'),
        ),
    ]
