# `contract_samples/` du module Facturation — PACT10 : le contrat part EN PREMIER

Chaque fichier est l'exemple PARTAGÉ d'une route facturation : la moitié serveur
(tests back) l'affirme, la moitié écran (tests front) l'importe — aucune des deux
n'invente la forme de l'autre. Lu par `scripts/check_api_shapes.py`. Montants en
TEXTE décimal (« 15000.00 »), jamais en nombre flottant.

| Fichier | Route | Tâche |
|---|---|---|
| `facture_encaissable.json` | `GET /api/django/ventes/factures/` — clés `encaissable` / `motif_non_encaissable` | AFAC2 (producteur AFAC9, écran AFAC10) |
| `releve_import_dry_run.json` | `POST /api/django/ventes/paiements/import-releve/dry-run/` — toutes les lignes, 9 statuts, file de revue | AFAC3 (producteurs AFAC5/AFAC6, écran AFAC7) |
| `releve_import_commit.json` | `POST /api/django/ventes/paiements/import-releve/commit/` — ligne ambiguë résolue `{ligne, facture_reference}`, bilan par ligne | AFAC3 (producteur AFAC6, écran AFAC7) |
| `lien_paiement.json` | `POST /api/django/ventes/factures/<pk>/lien-paiement/` — `pay_url` ABSOLU vers `/payer/<token>` | AFAC20 (producteurs AFAC21/AFAC23/AFAC24) |
| `paiement_public.json` | `GET /api/django/public/pay/<token>/` — page client « Payer » | AFAC20 (producteur AFAC21/AFAC24, écran AFAC26) |
| `note_debit_creation.json` | `POST /api/django/ventes/factures/<pk>/creer-note-debit/` — création partielle | AFAC20 (producteur AFAC32, écran AFAC33) |
| `facture_annulation.json` | `POST /api/django/ventes/factures/<pk>/annuler/` — directive `acompte` et refus `directive_acompte_requise` | AFAC1 (producteur AFAC12, écran AFAC13) |
| `paiement_annuler_saisie.json` | `POST /api/django/ventes/paiements/<pk>/annuler-saisie/` — état `annule_saisie` daté, motif, auteur | AFAC4 (producteur AFAC17, écran AFAC18) |
| `paiement_reaffecter.json` | `POST /api/django/ventes/paiements/<pk>/reaffecter/` — réaffectation vers une facture du même client | AFAC4 (producteur AFAC17, écran AFAC18) |
