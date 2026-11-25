# Tour 3 — remesure au calme des lenteurs des tours 1 et 2 (orchestrateur, 25/11/2026, ~01 h 10 UTC)

Constats visés : T4-V1-009 (S2), T4-V2-005 (S3), T4-V2-014 (S2) — pages blanches de 45 à 50 s, appels de 12 à 90 s.
Ces mesures avaient été prises pendant que quatre relecteurs (tour 1) puis deux relecteurs et des lanes de
construction partageaient l'instrument (un seul processus de tâches de fond, 16 Go de mémoire sur le poste).

Remesure SANS navigateur ni relecteur sur l'instrument (trois lanes de construction tournaient sur le poste), compte
Administrateur de la copie anonymisée, trois passes, mêmes routes que T4-V2-005 :

| Route | Passe 1 | Passe 2 | Passe 3 |
|---|---|---|---|
| connexion (`/token/`) | 0,9 s | — | — |
| liste des leads (25 lignes) | 1,3 s | — | — |
| `/auth/me/` | 0,1 s | 0,1 s | 0,1 s |
| fiche d'un lead | 0,3 s | 0,5 s | 0,2 s |
| `/crm/canaux/` | 0,1 s | 0,1 s | 0,1 s |
| `/notifications/attention-summary/` | 0,2 s | 0,1 s | 0,1 s |
| `/reporting/probabilites-etape/` | 0,2 s | 0,0 s | 0,0 s |
| `/crm/leads/doublons/` | 2,6 s | 2,4 s | 1,7 s |

Lecture : les durées de 12 à 59 s relevées aux tours 1 et 2 sur ces routes ne se reproduisent pas au calme
(0,0 à 0,5 s) : elles mesuraient la saturation de l'instrument, pas le produit. Seule `/crm/leads/doublons/` reste
lente par elle-même (1,7 à 2,6 s sur ~3 700 leads) — à suivre, sans gravité.
NON remesuré ici : le devis automatique (`POST /ventes/devis/auto/`, 14 à 98 s relevés), « Réviser », la génération
des PDF et `resultat/` du calepinage — à mesurer par les relecteurs du tour 3, deux à la fois, second essai compris.
