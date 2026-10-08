# `contract_samples/` du module Facturation — PACT10 : le contrat part EN PREMIER

Chaque fichier est l'exemple PARTAGÉ d'une route facturation : la moitié serveur
(tests back) l'affirme, la moitié écran (tests front) l'importe — aucune des deux
n'invente la forme de l'autre. Lu par `scripts/check_api_shapes.py`. Montants en
TEXTE décimal (« 15000.00 »), jamais en nombre flottant.

| Fichier | Route | Tâche |
|---|---|---|
| `facture_encaissable.json` | `GET /api/django/ventes/factures/` — clés `encaissable` / `motif_non_encaissable` | AFAC2 (producteur AFAC9, écran AFAC10) |
