"""Le calepinage 3D d'une AFFAIRE d'appel d'offres (miroir de ``Devis.roof_layout``).

Purement ADDITIVE et RÉVERSIBLE : une seule colonne JSON NULLABLE, sans défaut,
sans contrainte et sans index — aucune réécriture de ligne, aucun verrou long,
et ``migrate ao 0023`` la retire sans perte pour les données existantes.

``NULL`` est la valeur juste pour une affaire qui n'a jamais ouvert l'atelier
3D : un ``{}`` dirait « session enregistrée mais vide », ce qui est faux.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0023_toiture_origine_geo'),
    ]

    operations = [
        migrations.AddField(
            model_name='appeloffre',
            name='roof_layout',
            field=models.JSONField(blank=True, null=True, verbose_name='Calepinage 3D enregistré (layout du builder)'),
        ),
    ]
