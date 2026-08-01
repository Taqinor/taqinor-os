"""APX18 — Photo produit : `Produit.photo` → `records.Attachment` (MinIO).

La photo produit a été DÉGATÉE par mot fondateur du 2026-08-01 (« photos ok »).

ARC26 : aucune NOUVELLE pièce jointe ne passe par un `FileField`/`ImageField`
— la photo EST une `records.Attachment` (bucket MinIO `erp-uploads`), et ce
champ n'est que le POINTEUR vers LA photo canonique du produit (sans lui,
n'importe quelle pièce jointe image deviendrait « la » photo).

ADDITIVE et RÉVERTABLE : FK nullable/blank, `SET_NULL`, sans valeur par
défaut. Aucun produit existant n'est modifié, aucune lecture ni écriture
existante ne change de comportement, et un `migrate stock 0083` la retire
sans perte (les pièces jointes elles-mêmes restent intactes dans `records`).

La photo est INTERNE : elle alimente la vignette du catalogue et l'en-tête de
la fiche produit. Elle n'entre dans aucun PDF ni aucune sortie client-facing,
et n'est jamais rendue à côté de `prix_achat`.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0001_initial'),
        ('stock', '0083_ntprt25_fournisseur_statut_validation'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='photo',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='records.attachment',
                verbose_name='Photo produit',
                help_text='Pièce jointe MinIO servant de photo du produit — '
                          'écrans internes uniquement. Jamais sur un document '
                          'client.',
            ),
        ),
    ]
