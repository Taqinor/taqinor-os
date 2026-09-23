# CALX278 — taxes séparées des prix dans la grille société : déclaration
# « prix TTC / prix HT », taxes saisies avec leur source, charge minimale
# journalière. Migration ADDITIVE : ``prix_incluent_taxes`` vaut VRAI (la
# facture d'aujourd'hui, inchangée), le reste est vide par défaut.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0099_calx277_structures_tarif'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='charge_minimale_mad_jour',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Montant minimal facturé par jour, dans la même base que les prix (TTC ou HT).', max_digits=10, null=True, verbose_name='Charge minimale (par jour)'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='prix_incluent_taxes',
            field=models.BooleanField(default=True, help_text='Décocher si vos prix sont hors taxes : les taxes saisies ci-dessous seront alors appliquées.', verbose_name='Les prix saisis incluent les taxes'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='taxes',
            field=models.JSONField(blank=True, help_text='Liste [{libelle, taux_pct, assiette (energie|total), source}] — chaque taxe porte sa source.', null=True, verbose_name='Taxes de la facture'),
        ),
    ]
