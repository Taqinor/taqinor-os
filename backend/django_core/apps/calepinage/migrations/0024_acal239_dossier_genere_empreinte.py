# ACAL239 (C-ACAL-135) — l'empreinte des entrées à la génération d'un dossier
# réglementaire. Colonne additive à défaut vide : aucune réécriture de table,
# aucun backfill (aucun dossier généré en base). Réversible (RemoveField).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0023_acal118_archive_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossierreglementaire',
            name='genere_empreinte',
            field=models.CharField(
                blank=True, default='', max_length=64,
                verbose_name='Empreinte des entrées à la génération'),
        ),
    ]
