"""ACAL822 — date « vérifié le » et limites saisies d'un gabarit de dossier
réglementaire (dossier marocain générique, D-ACAL-43).

Additive : deux ``AddField`` (date nullable, liste vide par défaut), aucune
donnée écrite ; réversible.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0038_acal568_controles_pose'),
    ]

    operations = [
        migrations.AddField(
            model_name='gabaritdossierreglementaire',
            name='verifie_le',
            field=models.DateField(
                blank=True, null=True, verbose_name='Vérifié le'),
        ),
        migrations.AddField(
            model_name='gabaritdossierreglementaire',
            name='limites',
            field=models.JSONField(
                blank=True, default=list, verbose_name='Limites saisies'),
        ),
    ]
