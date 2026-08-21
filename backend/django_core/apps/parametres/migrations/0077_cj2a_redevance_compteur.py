"""CJ2a — redevance de location du compteur, réglage société (additive, NULL).

Aucune valeur par défaut : la redevance n'est publiée par aucun distributeur
marocain (recherche du 21/08/2026). NULL = inconnue = ignorée par le calcul,
soit exactement le comportement d'avant cette migration. Réversible sans perte.
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
                help_text="Montant exact lu sur votre facture réelle, ligne "
                          "location/entretien compteur. Laisser VIDE tant "
                          "qu'il n'a pas été relevé : vide = charge ignorée "
                          "(comportement actuel), jamais un montant supposé.",
                max_digits=7, null=True,
                verbose_name='Redevance location compteur (MAD/mois)'),
        ),
    ]
