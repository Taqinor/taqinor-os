# ODX19 — App Achats, étape 1 (modèles, state-only). Sort de stock les
# modèles PrixFournisseur, BonCommandeFournisseur + LigneBonCommandeFournisseur,
# ReceptionFournisseur + LigneReceptionFournisseur, FactureFournisseur +
# LigneFactureFournisseur, PaiementFournisseur, RetourFournisseur +
# LigneRetourFournisseur vers apps.achats (équivalent Odoo Purchase). Cette
# migration retire les 10 modèles de l'état stock (SeparateDatabaseAndState,
# ZÉRO SQL — les tables physiques `stock_*` restent inchangées). Ce DeleteModel
# est ordonné EN DERNIER (create → repoint → delete) : il dépend d'achats 0001
# (qui a déjà recréé les modèles dans l'état achats) ET de TOUS les re-pointages
# cross-app (compta 0111, installations 0096, ventes 0084), lesquels tirent
# transitivement les migrations HISTORIQUES qui référencent stock.<model>
# (compta 0009, installations 0018/0028/0030/0032/0075/0076, ventes 0047).
# Ainsi, lors d'un rejeu propre, AUCUNE migration historique référençant un
# modèle déplacé ne s'exécute APRÈS sa suppression de l'état (sinon
# `Related model 'stock.boncommandefournisseur' cannot be resolved`).
# Toutes les FK RELATIONNELLES portées par ces 10 modèles sont
# retirées avant leur DeleteModel (même recette que ODX9/ODX11 — évite toute
# référence pendante pendant le rejeu de l'état). Fournisseur, Produit,
# MouvementStock, EmplacementStock RESTENT dans stock (master data) ; les 5
# modèles stock restants qui pointent vers achats (PalierPrixFournisseur,
# EcheanceFactureFournisseur, AcompteFournisseur, AvoirFournisseur,
# ImputationAvoirFournisseur) sont re-pointés par 0080, APRÈS que achats 0001
# ait créé leurs cibles (achats.PrixFournisseur/BonCommandeFournisseur/
# FactureFournisseur/RetourFournisseur existent dans l'état à ce moment-là).
# Aucune donnée déplacée.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0078_zsal9_produit_avertissement_vente'),
        # ODX19 (correctif rejeu propre) — le DeleteModel tourne EN DERNIER :
        # après qu'achats 0001 ait créé les modèles dans l'état achats, et après
        # TOUS les re-pointages cross-app (qui tirent transitivement les
        # migrations historiques référençant stock.<model>). DAG garanti :
        # achats 0001 dépend de stock 0078 (pas de 0079) → aucun cycle.
        ('achats', '0001_odx19_achats_split'),
        ('compta', '0111_odx19_repoint_achats_crossapp'),
        ('installations', '0096_odx19_repoint_achats_crossapp'),
        ('ventes', '0084_odx19_repoint_achats_crossapp'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # ── PrixFournisseur ──────────────────────────────────────
                migrations.RemoveField(model_name='prixfournisseur', name='company'),
                migrations.RemoveField(model_name='prixfournisseur', name='produit'),
                migrations.RemoveField(model_name='prixfournisseur', name='fournisseur'),
                # ── BonCommandeFournisseur ───────────────────────────────
                migrations.RemoveField(model_name='boncommandefournisseur', name='company'),
                migrations.RemoveField(model_name='boncommandefournisseur', name='fournisseur'),
                migrations.RemoveField(model_name='boncommandefournisseur', name='emplacement_destination'),
                migrations.RemoveField(model_name='boncommandefournisseur', name='chantier_livraison'),
                migrations.RemoveField(model_name='boncommandefournisseur', name='chantier_origine'),
                migrations.RemoveField(model_name='boncommandefournisseur', name='acheteur'),
                migrations.RemoveField(model_name='boncommandefournisseur', name='created_by'),
                # ── LigneBonCommandeFournisseur ──────────────────────────
                migrations.RemoveField(model_name='ligneboncommandefournisseur', name='bon_commande'),
                migrations.RemoveField(model_name='ligneboncommandefournisseur', name='produit'),
                # ── ReceptionFournisseur ─────────────────────────────────
                migrations.RemoveField(model_name='receptionfournisseur', name='company'),
                migrations.RemoveField(model_name='receptionfournisseur', name='bon_commande'),
                migrations.RemoveField(model_name='receptionfournisseur', name='recu_par'),
                migrations.RemoveField(model_name='receptionfournisseur', name='created_by'),
                # ── LigneReceptionFournisseur ────────────────────────────
                migrations.RemoveField(model_name='lignereceptionfournisseur', name='reception'),
                migrations.RemoveField(model_name='lignereceptionfournisseur', name='ligne_commande'),
                migrations.RemoveField(model_name='lignereceptionfournisseur', name='produit'),
                # ── FactureFournisseur ───────────────────────────────────
                migrations.RemoveField(model_name='facturefournisseur', name='company'),
                migrations.RemoveField(model_name='facturefournisseur', name='fournisseur'),
                migrations.RemoveField(model_name='facturefournisseur', name='bon_commande'),
                migrations.RemoveField(model_name='facturefournisseur', name='resolu_par'),
                migrations.RemoveField(model_name='facturefournisseur', name='created_by'),
                # ── LigneFactureFournisseur ──────────────────────────────
                migrations.RemoveField(model_name='lignefacturefournisseur', name='facture'),
                migrations.RemoveField(model_name='lignefacturefournisseur', name='produit'),
                # ── PaiementFournisseur ──────────────────────────────────
                migrations.RemoveField(model_name='paiementfournisseur', name='company'),
                migrations.RemoveField(model_name='paiementfournisseur', name='facture'),
                migrations.RemoveField(model_name='paiementfournisseur', name='created_by'),
                # ── RetourFournisseur ─────────────────────────────────────
                migrations.RemoveField(model_name='retourfournisseur', name='company'),
                migrations.RemoveField(model_name='retourfournisseur', name='fournisseur'),
                migrations.RemoveField(model_name='retourfournisseur', name='bon_commande'),
                migrations.RemoveField(model_name='retourfournisseur', name='created_by'),
                # ── LigneRetourFournisseur ────────────────────────────────
                migrations.RemoveField(model_name='ligneretourfournisseur', name='retour'),
                migrations.RemoveField(model_name='ligneretourfournisseur', name='produit'),
                # ── DeleteModel (les 10 modèles, tables physiques inchangées) ──
                migrations.DeleteModel(name='PrixFournisseur'),
                migrations.DeleteModel(name='BonCommandeFournisseur'),
                migrations.DeleteModel(name='LigneBonCommandeFournisseur'),
                migrations.DeleteModel(name='ReceptionFournisseur'),
                migrations.DeleteModel(name='LigneReceptionFournisseur'),
                migrations.DeleteModel(name='FactureFournisseur'),
                migrations.DeleteModel(name='LigneFactureFournisseur'),
                migrations.DeleteModel(name='PaiementFournisseur'),
                migrations.DeleteModel(name='RetourFournisseur'),
                migrations.DeleteModel(name='LigneRetourFournisseur'),
            ],
            database_operations=[],
        ),
    ]
