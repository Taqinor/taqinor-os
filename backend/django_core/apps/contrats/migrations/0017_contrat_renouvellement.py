"""Migration additive CONTRAT23 — champs d'audit du renouvellement.

Ajoute sur ``Contrat`` deux champs nullable/par-défaut pour tracer les
renouvellements (manuels + tacites), sans toucher aux champs existants :

- ``date_dernier_renouvellement`` : date du dernier renouvellement effectif
  (NULL = jamais renouvelé) — sert aussi de garde d'idempotence à la tacite
  reconduction ;
- ``nb_renouvellements``          : compteur informatif (def. 0).

Purement additive et réversible (``RemoveField``). Aucune donnée existante n'est
modifiée (valeurs par défaut neutres : NULL et 0).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0016_alertecontrat"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrat",
            name="date_dernier_renouvellement",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Date du dernier renouvellement",
            ),
        ),
        migrations.AddField(
            model_name="contrat",
            name="nb_renouvellements",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Nombre de renouvellements"
            ),
        ),
    ]
