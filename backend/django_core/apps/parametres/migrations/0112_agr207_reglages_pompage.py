# AGR207 (Groupe AGR, 02/10/2026) — barème des charges solaires de pompage et
# règle FDA datée sur TariffSettings, VIDES par défaut ([] / {}), pour le
# calcul INTERNE. Migration additive et réversible.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0111_agr107_reglages_pompage'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='charges_pompage_solaire',
            field=models.JSONField(
                blank=True, default=list,
                help_text='Liste [{libelle, montant_mad_an, source}] — '
                          'nettoyage, visite annuelle… chaque charge porte '
                          'sa source.',
                verbose_name='Charges solaires de pompage (barème société)'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='regle_fda_pompage',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='{taux_pct, plafond_mad_par_ha, '
                          'plafond_mad_par_kwc, plafond_mad_par_projet, base '
                          '(ht|ttc|a_confirmer), source, releve_le} — '
                          'refusée sans source.',
                verbose_name='Règle FDA pompage (usage interne)'),
        ),
    ]
