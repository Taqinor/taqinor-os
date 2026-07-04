# Generated for XRH3 — Congés demi-journée + justificatif maladie.
#
# Entièrement additive : deux booléens + un FileField sur ``DemandeConge``,
# un PositiveIntegerField nullable sur ``TypeAbsence``. Réversible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0039_typeabsence_jours_legaux'),
    ]

    operations = [
        migrations.AddField(
            model_name='typeabsence',
            name='jours_max_sans_justificatif',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Jours max sans justificatif'),
        ),
        migrations.AddField(
            model_name='demandeconge',
            name='demi_journee_debut',
            field=models.BooleanField(
                default=False, verbose_name='Demi-journée (début)'),
        ),
        migrations.AddField(
            model_name='demandeconge',
            name='demi_journee_fin',
            field=models.BooleanField(
                default=False, verbose_name='Demi-journée (fin)'),
        ),
        migrations.AddField(
            model_name='demandeconge',
            name='justificatif',
            field=models.FileField(
                blank=True, null=True,
                upload_to='rh/demandes_conge/justificatifs/',
                verbose_name='Justificatif'),
        ),
    ]
