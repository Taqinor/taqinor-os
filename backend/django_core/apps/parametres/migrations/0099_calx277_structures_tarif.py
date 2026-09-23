# CALX277 — structure de la grille tarifaire société : tranches (défaut, la
# facture d'aujourd'hui), prix unique du kWh ou deux postes horaires, et le
# pays du tarif. Migration ADDITIVE : ``structure_tarif`` prend la valeur
# ``tranches`` (comportement inchangé), les prix sont vides par défaut.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0098_calx276_mecanisme_compensation'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='pays_tarif',
            field=models.CharField(blank=True, default='', max_length=2, verbose_name='Pays du tarif (code ISO à deux lettres)'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='poste_bas',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Prix du kWh en heures basses'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='poste_haut',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Prix du kWh en heures hautes'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='prix_unique_kwh',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Prix unique du kWh'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='structure_tarif',
            field=models.CharField(choices=[('tranches', 'Tranches de consommation (barème à paliers)'), ('prix_unique', 'Prix unique du kWh'), ('deux_postes', 'Deux postes horaires (heures hautes / basses)')], default='tranches', max_length=12, verbose_name='Structure du tarif'),
        ),
    ]
