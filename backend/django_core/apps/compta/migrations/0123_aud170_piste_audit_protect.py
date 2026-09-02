"""AUD170 — ``PisteAuditComptable.ecriture`` passe de CASCADE à PROTECT.

La piste d'audit est décrite « INALTÉRABLE » et « append-only », mais son
``OneToOneField`` vers l'écriture était en CASCADE : supprimer l'écriture
effaçait aussi le maillon censé prouver qu'elle n'a pas bougé.

ADDITIF ET RÉVERSIBLE : la migration ne change que la règle ``on_delete``
(contrainte de clé étrangère), aucune donnée n'est touchée ; ``git revert``
suffit à revenir à l'état antérieur.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0122_odx15_frais_split'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pisteauditcomptable',
            name='ecriture',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='piste_audit',
                to='compta.ecriturecomptable',
                verbose_name='Écriture',
            ),
        ),
    ]
