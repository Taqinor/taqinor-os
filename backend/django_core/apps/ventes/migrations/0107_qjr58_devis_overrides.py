"""QJR58 (audit L3 du 29/08/2026, décision fondateur D12) — LE REGISTRE de
surcharges d'un devis prend sa colonne.

Additive et réversible : un seul champ JSON nullable sur ``Devis``. Aucun
backfill, aucune valeur par défaut sur les lignes existantes — un devis
antérieur porte ``NULL`` et se comporte EXACTEMENT comme avant (aucun chemin
surchargé ⇒ la dérivation moteur fournit toutes les valeurs).

Ce champ ne stocke QUE des ENTRÉES (les choix du vendeur que le moteur ne peut
pas redériver), sous la forme ``{chemin: {valeur, pose_le, pose_par, origine}}``
— la liste blanche D12 est la seule porte
(``apps/ventes/domain/overrides.py``, contrat
``apps/ventes/contract_samples/devis_overrides.json``). Aucun nombre DÉRIVÉ
(total, ratio, économie, kWc) n'y entre jamais : c'est ce qui rend un prix
tapé à la main physiquement impossible dans ce registre.

Il REMPLACE le mécanisme historique ``saisie_manuelle`` (noms de champs à plat,
sans notion de dérivation ni d'audit ``pose_le``/``pose_par``), qui n'est plus
créé par aucun chemin de code.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0106_qjr52_prix_par_kwc_net'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='overrides',
            field=models.JSONField(
                blank=True, null=True,
                help_text="Registre des surcharges du vendeur, par CHEMIN "
                          "({valeur, pose_le, pose_par, origine}). Entrées "
                          "seules : aucun nombre calculé par le moteur n'y "
                          "entre jamais. Liste blanche : décision fondateur "
                          "D12 du 29/08/2026.",
                verbose_name='Surcharges du vendeur (par chemin)',
            ),
        ),
    ]
