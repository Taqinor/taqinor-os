"""NTMIG6 — ancre temporelle du rollback (annuler_lot).

Migration PUREMENT ADDITIVE : un ``AddField`` nullable sur une table
existante, aucun ``RunPython``, aucune donnée existante touchée. Le reverse
est le DROP COLUMN standard de Django.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('migration', '0006_ntmig31_parcours_certification'),
    ]

    operations = [
        migrations.AddField(
            model_name='lotmigration',
            name='dernier_chargement_debut_at',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Début du dernier chargement'),
        ),
    ]
