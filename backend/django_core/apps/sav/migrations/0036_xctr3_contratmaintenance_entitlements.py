# XCTR3 — Droits inclus (entitlements) du contrat de maintenance.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0035_xctr2_contratmaintenance_equipements'),
    ]

    operations = [
        migrations.AddField(
            model_name='contratmaintenance',
            name='visites_incluses_an',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Nombre de visites (tickets PREVENTIF) incluses '
                          'par année civile. Vide = illimité.',
                verbose_name='Visites incluses / an'),
        ),
        migrations.AddField(
            model_name='contratmaintenance',
            name='deplacements_inclus_an',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Nombre de déplacements (tickets CORRECTIF) inclus '
                          'par année civile. Vide = illimité.',
                verbose_name='Déplacements inclus / an'),
        ),
        migrations.AddField(
            model_name='contratmaintenance',
            name='pieces_couvertes_pct',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text='Pourcentage (0–100) du coût des pièces couvert '
                          'par le contrat. Vide = indéfini.',
                verbose_name='Pièces couvertes (%)'),
        ),
    ]
