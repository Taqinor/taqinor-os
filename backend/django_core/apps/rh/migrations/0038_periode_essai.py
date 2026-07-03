# Generated for XRH1 — Période d'essai (suivi + alerte).
#
# Entièrement additive : deux champs nullable/par défaut faux sur
# ``DossierEmploye``. Réversible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0037_note_de_frais'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossieremploye',
            name='essai_date_fin',
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Fin de période d'essai"),
        ),
        migrations.AddField(
            model_name='dossieremploye',
            name='essai_renouvele',
            field=models.BooleanField(
                default=False,
                verbose_name="Période d'essai renouvelée"),
        ),
    ]
