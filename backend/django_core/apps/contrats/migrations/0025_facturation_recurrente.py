"""Migration additive : facturation récurrente (CONTRAT31).

Ajoute deux champs ADDITIFS :
- ``EcheancierContrat.facturation_active`` (BooleanField, défaut False) : marque
  un échéancier comme alimentant la facturation récurrente. Tant qu'il est faux,
  AUCUNE facture n'est émise.
- ``LigneEcheance.facture_id`` (PositiveIntegerField nullable) : lien LÂCHE (id
  seul, jamais un FK dur ni un import de ``ventes.models``) vers la
  ``ventes.Facture`` émise pour l'échéance — sert aussi de garde d'idempotence.

L'émission elle-même (``services.facturer_ligne_echeance``) passe par la
frontière cross-app (client résolu via ``crm.selectors``, numérotation via
``ventes.utils.references``) et ne touche jamais le ``Contrat.statut`` (CONTRAT12)
ni le funnel ``STAGES.py`` (rule #2). Entièrement réversible (``RemoveField``).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0024_echeancier"),
    ]

    operations = [
        migrations.AddField(
            model_name="echeanciercontrat",
            name="facturation_active",
            field=models.BooleanField(
                default=False,
                verbose_name="Facturation récurrente active",
            ),
        ),
        migrations.AddField(
            model_name="ligneecheance",
            name="facture_id",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="ID de la facture émise",
            ),
        ),
    ]
