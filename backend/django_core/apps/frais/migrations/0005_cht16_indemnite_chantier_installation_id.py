# CHT16 — indemnités de frais rattachées au vrai chantier. ADDITIF STRICT :
# nouveau champ `installation_id` (loose ref, nullable) sur IndemniteChantier.
# Aucune FK, aucune dépendance vers l'app `installations` (frontière
# cross-app respectée — table physique `compta_indemnitechantier` inchangée,
# ODX15).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frais', '0004_notefrais_justificatif_filename_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='indemnitechantier',
            name='installation_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Chantier (id)'),
        ),
    ]
