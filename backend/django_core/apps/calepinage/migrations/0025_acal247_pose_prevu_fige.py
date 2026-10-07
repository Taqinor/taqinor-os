# ACAL247 (C-ACAL-139) — le prévu de la conception figé à la saisie du relevé
# de pose. Colonnes additives (nullable / défaut vide) : aucune réécriture de
# table, SANS backfill (un prévu rejoué après coup serait un chiffre inventé).
# Réversible (RemoveField).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0024_acal239_dossier_genere_empreinte'),
    ]

    operations = [
        migrations.AddField(
            model_name='posereelle',
            name='modules_prevus',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Modules prévus au relevé'),
        ),
        migrations.AddField(
            model_name='posereelle',
            name='prevu_source',
            field=models.CharField(
                blank=True, default='', max_length=20,
                verbose_name='Source du prévu figé'),
        ),
    ]
