# ODX19 — App Achats, étape 1 (modèles, state-only). Sort de stock les
# modèles PrixFournisseur, BonCommandeFournisseur + LigneBonCommandeFournisseur,
# ReceptionFournisseur + LigneReceptionFournisseur, FactureFournisseur +
# LigneFactureFournisseur, PaiementFournisseur, RetourFournisseur +
# LigneRetourFournisseur vers apps.achats (équivalent Odoo Purchase). Cette
# migration retire les 10 modèles de l'état stock (SeparateDatabaseAndState,
# ZÉRO SQL — les tables physiques `stock_*` restent inchangées) ; achats 0001
# les recrée dans l'état sur les MÊMES tables juste après (dépendance
# explicite). Toutes les FK RELATIONNELLES portées par ces 10 modèles sont
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
