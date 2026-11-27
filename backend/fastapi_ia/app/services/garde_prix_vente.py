"""D-ACAL-165 (fondateur, 26/11/2026) — famille PRIX DE VENTE du chatbot SQL.

Refusee a qui ne porte pas `prix_vente_voir` (Technicien, Technicien
responsable), meme garde que le prix d'achat de `sql_agent_service` (colonne
nommee OU projection ligne entiere, sur l'arbre sqlglot :
`_references_forbidden_column(..., allow_sale=False)`). Colonnes du catalogue
(stock.Produit) et montants des devis / lignes de devis, verifies sur les
modeles Django : LigneDevis.prix_unitaire / remise, Devis.remise_globale,
prix_cible_kwc, prix_par_kwc, total_affiche_range. Compte sans role fin et
superuser (`permissions=None`) : regle inchangee. Lot 8, relecture finale :
le contrat de maintenance (sav.ContratMaintenance.prix, et `valeur_annuelle`
que le serialiseur et l'explorateur de donnees en tirent), masque aux comptes
sans `prix_vente_voir` (`apps/sav/bi_datasets.py`), l'est aussi ici — un role
personnalise `sav_voir` sans le code ne le lit plus par l'assistant SQL. Seule
table autorisee portant une colonne `prix` (verifie sur `_ALLOWED_TABLES`).

Module a part : `sql_agent_service.py` depasse 2 000 lignes et ne grossit pas
(garde C20 FICHIER_MUR).
"""
from __future__ import annotations

COLONNES = (
    "prix_vente", "paliers_prix_vente", "prix_fixe_ht", "prix_par_panneau_ht",
    "tarif_location_jour", "tarif_location_semaine", "tarif_location_mois",
    "prix_unitaire", "remise", "remise_globale", "prix_cible_kwc",
    "prix_par_kwc", "total_affiche_range",
    "prix", "valeur_annuelle",  # sav_contratmaintenance (relecture finale lot 8)
)
TABLES = ("stock_produit", "ventes_lignedevis", "ventes_devis", "sav_contratmaintenance")


def permet_prix_vente(permissions) -> bool:
    """`permissions=None` (superuser, compte sans role fin, appel direct) :
    inchange ; sinon le code `prix_vente_voir` decide."""
    return permissions is None or "prix_vente_voir" in permissions


def verifier_droits_de_lecture(sql: str, permissions) -> None:
    """Prix de vente (D-ACAL-165), puis droit de module et portee (ALEC16,
    `_verifier_module_et_portee`, inchange). Leve `RefusDeDroit`."""
    from app.services import sql_agent_service as svc

    if not permet_prix_vente(permissions) and svc._references_forbidden_column(
            sql, allow_price=True, allow_sale=False):
        raise svc.RefusDeDroit("Prix de vente (prix_vente_voir) — lecture refusee.")
    svc._verifier_module_et_portee(sql, permissions)
