# Generated for XRH2 — Types d'absence légaux Maroc pré-configurés (seed).
#
# Entièrement additive : un champ nullable informatif sur ``TypeAbsence``.
# Réversible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0038_periode_essai'),
    ]

    operations = [
        migrations.AddField(
            model_name='typeabsence',
            name='jours_legaux',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=6, null=True,
                verbose_name='Plafond légal (jours, informatif)'),
        ),
    ]
