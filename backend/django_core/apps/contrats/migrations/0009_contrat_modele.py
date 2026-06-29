"""Migration additive : FK optionnelle ``Contrat.modele`` → ``ModeleContrat``.

CONTRAT10 (génération par fusion) : garder une trace du gabarit dont un contrat
est issu permet de fusionner ses jetons dans le corps du modèle au moment du
rendu. La FK est NULLABLE et ``on_delete=SET_NULL`` — supprimer un gabarit ne
supprime jamais le contrat instancié, il perd seulement le lien (le rendu
retombe alors sur le gabarit par défaut). Entièrement additive et réversible.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0008_clausecontrat"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrat",
            name="modele",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="contrats_instancies",
                to="contrats.modelecontrat",
                verbose_name="Modèle source",
            ),
        ),
    ]
