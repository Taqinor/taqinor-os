# ODX17 — App Facturation, étape 1 (modèles, state-only).
#
# Sort Facture/LigneFacture/Paiement/Avoir/LigneAvoir/FollowupLevel/RelanceLog
# vers ``apps.facturation`` (équivalent Odoo Invoicing, séparé de Sales) SANS
# toucher aux tables : ``db_table`` figé sur les noms ``ventes_*`` actuels,
# migration ``SeparateDatabaseAndState`` (state_operations uniquement, zéro
# SQL, révertable). Même recette que ODX9/ODX11/ODX12/ODX13.
#
# Avant de retirer les 7 modèles de l'état ventes, on RE-POINTE (AlterField,
# state-only) les modèles qui RESTENT dans ventes mais référencent
# Facture/Paiement (FactureActivity, FactureSource, AffectationPaiement,
# NoteDebit, RetenueSubie, PromessePaiement, EmailLog, ShareLink, PaymentLink,
# LigneRemiseEncaissement, TentativeDebitMandat) vers 'facturation.Facture' /
# 'facturation.Paiement'.
#
# ODX17 (correctif rejeu propre) — ce DeleteModel est ordonné EN DERNIER
# (create → repoint → delete) : il dépend de facturation 0001 (qui a déjà
# recréé les 7 modèles dans l'état facturation, sur les tables ventes_*
# inchangées) ET du re-pointage cross-app pos 0002 (qui tire transitivement
# pos 0001, seule migration HISTORIQUE hors-ventes référençant ventes.facture).
# Ainsi, lors d'un rejeu propre, aucune migration historique référençant un
# modèle déplacé ne s'exécute APRÈS sa suppression de l'état (sinon
# `Related model 'ventes.facture' cannot be resolved`). Les AlterField
# ci-dessous pointent vers facturation.* qui existe déjà dans l'état à ce stade.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0082_vx98_updated_by'),
        # ODX17 (correctif rejeu propre) — le DeleteModel tourne EN DERNIER :
        # après que facturation 0001 ait créé les 7 modèles dans l'état
        # facturation, et après le re-pointage cross-app pos 0002 (qui tire
        # transitivement pos 0001, historique référençant ventes.facture).
        # DAG garanti : facturation 0001 dépend de ventes 0082 (pas de 0083) et
        # pos 0002 dépend de facturation 0001 → aucun cycle.
        ('facturation', '0001_odx17_facturation_split'),
        ('pos', '0002_odx17_facture_facturation_ref'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # ── Re-pointer les modèles qui RESTENT dans ventes vers
                # 'facturation.Facture' / 'facturation.Paiement' ──
                migrations.AlterField(
                    model_name='factureactivity',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='activites', to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='facturesource',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='sources', to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='affectationpaiement',
                    name='paiement',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='affectations', to='facturation.paiement'),
                ),
                migrations.AlterField(
                    model_name='affectationpaiement',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='affectations_paiement',
                        to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='notedebit',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='notes_debit', to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='retenuesubie',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='retenues_subies',
                        to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='retenuesubie',
                    name='paiement',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='retenues_subies',
                        to='facturation.paiement'),
                ),
                migrations.AlterField(
                    model_name='promessepaiement',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='promesses_paiement',
                        to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='emaillog',
                    name='facture',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='email_logs', to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='sharelink',
                    name='facture',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='share_links', to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='paymentlink',
                    name='facture',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='payment_links', to='facturation.facture'),
                ),
                migrations.AlterField(
                    model_name='paymentlink',
                    name='paiement',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='payment_links', to='facturation.paiement'),
                ),
                migrations.AlterField(
                    model_name='ligneremiseencaissement',
                    name='paiement',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='lignes_remise_encaissement',
                        to='facturation.paiement'),
                ),
                migrations.AlterField(
                    model_name='tentativedebitmandat',
                    name='paiement',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='tentatives_debit_mandat',
                        to='facturation.paiement'),
                ),

                # ── Détacher les champs relationnels des 7 modèles PARTANTS ──
                migrations.RemoveField(model_name='facture', name='company'),
                migrations.RemoveField(model_name='facture', name='bon_commande'),
                migrations.RemoveField(model_name='facture', name='devis'),
                migrations.RemoveField(model_name='facture', name='lead'),
                migrations.RemoveField(model_name='facture', name='condition_paiement_ref'),
                migrations.RemoveField(model_name='facture', name='abandon_par'),
                migrations.RemoveField(model_name='facture', name='created_by'),
                migrations.RemoveField(model_name='facture', name='updated_by'),
                migrations.RemoveField(model_name='lignefacture', name='facture'),
                migrations.RemoveField(model_name='lignefacture', name='produit'),
                migrations.RemoveField(model_name='lignefacture', name='source_devis'),
                migrations.RemoveField(model_name='paiement', name='company'),
                migrations.RemoveField(model_name='paiement', name='facture'),
                migrations.RemoveField(model_name='paiement', name='client'),
                migrations.RemoveField(model_name='paiement', name='created_by'),
                migrations.RemoveField(model_name='avoir', name='company'),
                migrations.RemoveField(model_name='avoir', name='facture'),
                migrations.RemoveField(model_name='avoir', name='client'),
                migrations.RemoveField(model_name='avoir', name='created_by'),
                migrations.RemoveField(model_name='ligneavoir', name='avoir'),
                migrations.RemoveField(model_name='ligneavoir', name='produit'),
                migrations.RemoveField(model_name='followuplevel', name='company'),
                migrations.RemoveField(model_name='relancelog', name='company'),
                migrations.RemoveField(model_name='relancelog', name='facture'),
                migrations.RemoveField(model_name='relancelog', name='created_by'),

                # ── Retirer les 7 modèles de l'état ventes ──
                migrations.DeleteModel(name='LigneFacture'),
                migrations.DeleteModel(name='LigneAvoir'),
                migrations.DeleteModel(name='Paiement'),
                migrations.DeleteModel(name='Avoir'),
                migrations.DeleteModel(name='RelanceLog'),
                migrations.DeleteModel(name='FollowupLevel'),
                migrations.DeleteModel(name='Facture'),
            ],
            database_operations=[],
        ),
    ]
