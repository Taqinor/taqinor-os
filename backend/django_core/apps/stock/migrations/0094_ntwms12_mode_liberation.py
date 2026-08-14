"""NTWMS12 — règles de libération de vague (wave release strategy).

Additif et réversible :
  * ``VaguePicking.mode_liberation`` (défaut MANUEL = comportement historique
    strict : une vague ne part que sur clic) + ``seuil_lignes`` ;
  * ``AchatsParametres.heure_coupure_vagues`` — l'heure de coupure PAR SOCIÉTÉ,
    posée sur le singleton de réglages déjà propriété de `stock` (les apps de
    fondation `authentication`/`parametres` restent hors périmètre). NULL =
    aucune libération automatique.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0093_ntwms11_audit_scan_emballage'),
    ]

    operations = [
        migrations.AddField(
            model_name='vaguepicking',
            name='mode_liberation',
            field=models.CharField(
                choices=[('manuel', 'Manuel'),
                         ('auto_heure', "Automatique à l'heure de coupure"),
                         ('auto_seuil', 'Automatique au seuil de lignes')],
                default='manuel', max_length=20),
        ),
        migrations.AddField(
            model_name='vaguepicking',
            name='seuil_lignes',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='NTWMS12 — nombre de lignes déclenchant la '
                          'libération en mode AUTO_SEUIL. Vide = jamais '
                          'déclenché.',
                null=True),
        ),
        migrations.AddField(
            model_name='achatsparametres',
            name='heure_coupure_vagues',
            field=models.TimeField(
                blank=True,
                help_text='NTWMS12 — heure de coupure quotidienne à laquelle '
                          'les vagues en mode AUTO_HEURE sont lancées. Vide = '
                          'pas de libération automatique.',
                null=True),
        ),
    ]
