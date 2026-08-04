"""NTADM2 — champ `entite` OPTIONNEL sur facturation.Facture.

`Facture` vit dans ``apps.facturation`` depuis ODX17 (table historique
``ventes_facture`` préservée) ; le ré-export ``apps.ventes.models.Facture``
reste valable. Additif pur : colonne nullable, aucun backfill. NULL =
« non affecté » — comportement identique à aujourd'hui.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entites', '0001_initial'),
        ('facturation', '0002_odx17_rename_stale_contenttypes'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='entite',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='facturation_factures',
                to='entites.entite',
                verbose_name='Entité'),
        ),
    ]
