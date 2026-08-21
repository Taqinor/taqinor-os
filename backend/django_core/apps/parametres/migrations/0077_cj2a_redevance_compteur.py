"""CJ2a — charges fixes de l'abonnement, réglage société (additive, NULL).

NULL = appliquer le défaut SOURCÉ sur les factures réelles du fondateur
(location du compteur 18,28 HT + entretien du branchement 15,00 HT), codé dans
apps/ventes/quote_engine/bareme.py. Le champ n'existe que pour qu'une société
d'une autre zone substitue ses propres relevés. Réversible sans perte.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0076_companyprofile_delais_commerciaux'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='redevance_compteur_mad_mois',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text="Total TTC des lignes fixes de votre facture "
                          "(location du compteur + entretien du branchement). "
                          "Laisser VIDE pour appliquer le défaut relevé sur "
                          "facture réelle (39,94 MAD TTC/mois en 2026) ; "
                          "renseigner pour le remplacer par vos propres "
                          "montants.",
                max_digits=7, null=True,
                verbose_name='Charges fixes abonnement (MAD TTC/mois)'),
        ),
    ]
