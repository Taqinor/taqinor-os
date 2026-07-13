# ODX19 — re-pointe les FK des modèles stock RESTANTS (PalierPrixFournisseur,
# EcheanceFactureFournisseur, AcompteFournisseur, AvoirFournisseur,
# ImputationAvoirFournisseur) vers leurs cibles désormais dans apps.achats.
# Doit s'exécuter APRÈS achats 0001 (qui crée PrixFournisseur/
# BonCommandeFournisseur/FactureFournisseur/RetourFournisseur dans l'état
# achats) — d'où la dépendance explicite ci-dessous. State-only,
# SeparateDatabaseAndState, ZÉRO SQL (les colonnes/contraintes physiques
# `*_id` ne changent pas, seule l'étiquette de modèle Django change côté
# état). Aucune donnée déplacée.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0079_odx19_achats_split'),
        ('achats', '0001_odx19_achats_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='palierprixfournisseur',
                    name='prix_fournisseur',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='paliers', to='achats.prixfournisseur'),
                ),
                migrations.AlterField(
                    model_name='echeancefacturefournisseur',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='echeances', to='achats.facturefournisseur'),
                ),
                migrations.AlterField(
                    model_name='acomptefournisseur',
                    name='bon_commande',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='acomptes', to='achats.boncommandefournisseur'),
                ),
                migrations.AlterField(
                    model_name='acomptefournisseur',
                    name='facture_imputee',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='acomptes_imputes',
                        to='achats.facturefournisseur'),
                ),
                migrations.AlterField(
                    model_name='avoirfournisseur',
                    name='facture_origine',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='avoirs_origine',
                        to='achats.facturefournisseur'),
                ),
                migrations.AlterField(
                    model_name='avoirfournisseur',
                    name='retour',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='avoirs', to='achats.retourfournisseur'),
                ),
                migrations.AlterField(
                    model_name='imputationavoirfournisseur',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='avoirs_imputes',
                        to='achats.facturefournisseur'),
                ),
            ],
            database_operations=[],
        ),
    ]
