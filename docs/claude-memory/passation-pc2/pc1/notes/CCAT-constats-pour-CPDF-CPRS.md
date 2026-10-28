# CCAT — constats pour CPDF / CPRS (28/10, PC2) — hors périmètre catalogue

Les fiches catalogue portent des LIGNES DE DONNÉES lues par le code, dans `Produit.description` :
- « Modèle supposé : Huawei SUN2000-50KTL-M3 — à confirmer fondateur » (seed_catalogue.MODELE_SUPPOSE_PVG4 ; aucun lecteur, testé par apps/stock/tests.py:416 et ventes/tests/test_pv85_identites_schema.py:119)
- « Modèle confirmé fondateur : … » (lu par ventes/electrical_service.MARQUEUR_MODELE_CONFIRME)
- « Plage batterie : 40-60 V » / « Plage batterie : aucune (onduleur réseau) » (lu par stock.selectors.MARQUEUR_PLAGE_BATTERIE)
`quote_engine/lignes_classement.py` (~l.283) recopie la description BRUTE dans l'item ; `generate_devis_premium._desc_lines_html`
imprime ses lignes (max_lines) → incertitude + jargon interne (« fondateur ») au PDF et à la page publique.
Correctif recommandé côté rendu (propriétaire moteur/devis) : filtrer les lignes qui commencent par ces 3 marqueurs avant de servir
`description` au client (une fonction pure, testée sur les 3 préfixes). Ne PAS réécrire le catalogue : 2 marqueurs sont des données.
Aussi : désignations « … C&I » (« Coffret DC C&I », « Structure … C&I », prestations « … C&I ») = noms des articles semés
(`_articles_ci.py`), recopiés en désignation de ligne → « C&I » au client. Renommer touche l'unicité (company, nom) et le seeder
idempotent par nom/sku : à trancher à la composition (désignation client sans « C&I ») plutôt qu'au catalogue.
