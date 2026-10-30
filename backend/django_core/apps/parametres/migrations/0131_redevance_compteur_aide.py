"""ERR-PARAM-REDEVANCE-COMPTEUR — texte d'aide dit la vraie règle (état seul)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0130_amot64_productible_nullable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tariffsettings',
            name='redevance_compteur_mad_mois',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text="Total TTC des lignes fixes de votre facture "
                          "(location du compteur + entretien du branchement). "
                          "Sert à retirer l'abonnement d'un montant de facture "
                          "avant de le convertir en kWh. Aucun défaut n'est "
                          "appliqué à la conversion : VIDE = conversion "
                          "refusée ; saisir 0 si votre facture n'en porte "
                          "pas.",
                max_digits=7, null=True,
                verbose_name='Charges fixes abonnement (MAD TTC/mois)'),
        ),
    ]
