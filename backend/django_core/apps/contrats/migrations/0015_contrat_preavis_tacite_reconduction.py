"""Migration additive CONTRAT20 — dates clés (préavis) & tacite reconduction.

Ajoute sur ``Contrat`` quatre champs nullable/par-défaut, sans toucher aux
``date_debut``/``date_fin`` existants :

- ``preavis_jours``           : délai de préavis en jours avant la fin (NULL OK) ;
- ``tacite_reconduction``     : le contrat se renouvelle-t-il tacitement (def. False) ;
- ``duree_reconduction_mois`` : durée d'une période de reconduction en mois (NULL OK) ;
- ``preavis_traite``          : l'échéance de préavis a-t-elle déjà été traitée (def. False).

Purement additive et réversible (``RemoveField``). Aucune donnée existante n'est
modifiée (valeurs par défaut neutres).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0014_versioncontrat"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrat",
            name="preavis_jours",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Préavis (jours avant la fin)",
            ),
        ),
        migrations.AddField(
            model_name="contrat",
            name="tacite_reconduction",
            field=models.BooleanField(
                default=False, verbose_name="Tacite reconduction"
            ),
        ),
        migrations.AddField(
            model_name="contrat",
            name="duree_reconduction_mois",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Durée de reconduction (mois)",
            ),
        ),
        migrations.AddField(
            model_name="contrat",
            name="preavis_traite",
            field=models.BooleanField(
                default=False, verbose_name="Préavis traité"
            ),
        ),
    ]
