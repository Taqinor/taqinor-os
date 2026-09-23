# CALX279 — indexation annuelle du tarif SAISIE par la société avec sa source.
# Tranche la contradiction interne (6 %/an de l'étude bancable contre 0 % de
# la décision fondateur) : sans saisie, toute projection est à tarif constant
# avec la mention « aucune indexation saisie ». Migration ADDITIVE, deux
# champs vides par défaut.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0100_calx278_taxes_grille'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='indexation_source',
            field=models.TextField(blank=True, default='', help_text="Obligatoire dès qu'un taux est saisi (historique des tarifs publiés, contrat, étude).", verbose_name="Source de l'indexation"),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='indexation_tarif_pct_an',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='Indexation annuelle du tarif (%/an)'),
        ),
    ]
