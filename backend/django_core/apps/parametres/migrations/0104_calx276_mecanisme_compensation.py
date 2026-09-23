# CALX276 — mécanisme de compensation du surplus TYPÉ et SAISI par la société
# (injection totale / surplus / net-metering avec report), avec sa période de
# report, son plafond annuel et son ratio. Migration ADDITIVE : quatre champs
# vides par défaut, aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0103_calx274_tranches_tarifs'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='mecanisme_compensation',
            field=models.CharField(blank=True, choices=[('injection_totale', 'Injection totale (toute la production vendue)'), ('surplus', 'Surplus (autoconsommation + vente du surplus)'), ('net_metering_report', 'Net-metering avec report de crédit')], default='', help_text="Vide = le surplus injecté n'est pas valorisé. À choisir selon votre contrat de raccordement.", max_length=24, verbose_name='Mécanisme de compensation du surplus'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='plafond_annuel_kwh',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Plafond annuel d’énergie compensée (kWh)'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='ratio_compensation',
            field=models.DecimalField(blank=True, decimal_places=4, help_text='1 = un kWh injecté compense un kWh soutiré.', max_digits=5, null=True, verbose_name='Ratio de compensation (0 à 1)'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='report_periode',
            field=models.PositiveSmallIntegerField(blank=True, help_text="Net-metering avec report : pendant combien de mois un crédit d'énergie reste reportable.", null=True, verbose_name='Période de report du crédit (mois)'),
        ),
    ]
