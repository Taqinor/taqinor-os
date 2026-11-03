# Audit PA1 « contact-visite » — 2026-11-03 — L3
<!-- dossier-v3 | groupe: ACVI | base: 352ae54 | fraicheur: 352ae54 | constats: 0 | taches: 0 | decisions: 0 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PA1 (pilote crm / lead) : lu `apps/crm/**` (portes, webhooks, leads_*, cadence_*, receivers, tasks, selectors, views, serializers), `apps/visites/**`, `apps/contact/**`, `apps/dataimport/{services,views,export_views}.py`, `apps/roles/permissions_registre.py`, `authentication/permissions.py`, `core/{scoping,events}.py`, `frontend/src/{pages,features}/crm/**`, `frontend/src/pages/visites/**`, `frontend/src/features/visites/**` ; table `PA1.json` |
| Niveau | L3 — parcours chaud (416 commits crm/visites depuis le 20/10, cadence v4 mergée les 01-02/11) + sorties client (WhatsApp, e-mail, accusés) + multi-société et rôles + 13 portes |
| Données | demo (société `demo_admin` et une seconde société pour les 404) ; anon : non requis (chaque sonde crée ses données ou joue sur la démo en transaction annulée) ; prod lecture seule : aucune |
| Critères retenus | C1, C2, C3, C5, C6, C7, C8, C9, C10, C13, C14, C15, C16, C17, C18, C19, C20 |
| Étapes | PA1.01 portes de création (13) · PA1.02 qualification · PA1.03 cadence de contact · PA1.04 réponses et messages · PA1.05 visite planifiée · PA1.06 visite terminée · PA1.07 revue de visite · PA1.08 passages de main aval (devis, signé, perdu, Froid, archivage, fusion) |
| NE PAS REFAIRE | CADV5-114 ouverts (cadence v4 : 9, 10, 11, 22-30, 32, 34-36, 41, 50, 61, 62, 67, 72-74, 77-81, 85-91, 101-103, 105, 106, 108, 109, 112-114) ; CADV23/24/85 (gabarits par migration) ; ALEA56-58 ; AACQ107 ; ADVS23/24/42/44 ; AARG47 ; CRXB1-8 (GATED) ; PUB107-109, QXG1 (D-WHATSAPP) ; CADM1-8 ; ASEC1-64 ; APRF25 ; AANA67 |
| Non-objectifs | apps parquées (47) ; salles de vente et apporteurs (parqués, D-ACRM-6) ; WhatsApp Cloud API (D-WHATSAPP) ; écrans en navigateur (le live joue l'API) ; textes darija (CADM1) |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
Détecteurs : (à compléter).
Live : (à compléter).

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
Porte : (à compléter).

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|

## 7. Optionnel (jamais une tâche)

## 8. Limites, non couvert, écarts
- Non couvert : (à compléter).
- Écart à la méthode : (à compléter).
- Incident prod : aucun.

## 9. Coût et routage
Coût : H1 S4 O6 F1 · jetons sous-agents ≈ 0,0 M · tâches 0 (M0 0 M1 0 M2 0 M3 0 GATED 0).
Routage : (à compléter).
