# CIQ211 (Groupe CIQ, 03/10/2026) — réglages C&I SANS valeur par défaut sur
# TariffSettings : scénarios de sensibilité saisis (liste vide) et mention
# « crédit-bail » (fausse) + référence de l'avis juridique. Migration additive
# et réversible (RemoveField sans perte : colonnes neuves).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0119_ciq622_reglages_ci'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='sensibilites_ci',
            field=models.JSONField(
                blank=True, default=list,
                help_text='Liste [{cle (indexation_tarif|degradation|'
                          'tarif_kwh|production), variation_pct, source}] — '
                          'vide par défaut.',
                verbose_name='Scénarios de sensibilité C&I'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='mention_credit_bail_autorisee',
            field=models.BooleanField(
                default=False,
                verbose_name='Mention « crédit-bail » autorisée'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='mention_credit_bail_source',
            field=models.TextField(
                blank=True, default='',
                help_text='Obligatoire pour autoriser la mention '
                          '« crédit-bail ».',
                verbose_name="Référence de l'avis juridique (crédit-bail)"),
        ),
    ]
