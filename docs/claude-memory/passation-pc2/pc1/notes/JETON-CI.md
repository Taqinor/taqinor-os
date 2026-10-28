# JETON CI — une seule CI à la fois dans toute la flotte (ordre fondateur, Reda, 27/10/2026 16:25 Casablanca)

« maximum is one CI per session, and you keep monitoring, no 2 CI at the same time ! but you think wisely on who goes
first and who keeps building »

Règle : **personne ne pousse sans le jeton.** La coordinatrice le donne par message « JETON <CODE> ». Le détenteur
fait UN push (sa PR à jour de `main`, contrôles locaux verts, critique Fable rendue), met la PR en file
(`gh pr merge <n> --auto --merge`) et suit sa CI jusqu'au merge ; un rouge se corrige par UN push sous le même jeton.
Au merge, le jeton passe au suivant. Tout le monde d'autre **construit en local** : commits, contrôles locaux, critiques
Fable, rendus réels — sans push.

Les runs déjà lancés avant 16:25 finissent seuls ; aucune nouvelle poussée sans jeton.

## Ordre des jetons (révisé par la coordinatrice à chaque passage)

| # | PR | Session | Pourquoi cet ordre |
|---|----|---------|--------------------|
| 0 | #1086 | AGM (agent) | en tête de file, checks en cours — on la laisse atterrir |
| 1 | #1080 | CORC | gardienne de pile ; aperçu/devis_auto/option_avec dont dépendent CPDF, CPRS, CVL |
| 2 | #1096 | CEC | correctif de justesse : devis envoyés protégés par le niveau 3 (audit Fable) |
| 3 | #1084 | CLD | moteur C&I taille/profil (vagues 1+2) — la boulangerie |
| 4 | #1095 | RHOR | moteur horaire résidentiel (vagues 2+3) ; libère RPDF (recapteur) |
| 5 | #1094 | CMP | option batterie + vague 3 (30° toit plat) repliée AVANT le push |
| 6 | #1097 | CQST | contrat questionnaire (producteur) — RWEB/AGV l'attendent |
| 7 | #1101 | AGM v2 | déjà poussée, branchée sur #1086 ; ne coûte que le run de file |
| 7b | PR | CSV | script d'appel C&I (CSV1-7) + stabilisation du test relances instable ; indépendante, petite |
| 7c | PR vague 2 | CORC | CORC5/6/7/12 (série horaire au point de la ville → rend effectifs les réglages CMP sans GPS) + chaines_max_par_mppt ; #1080 mergée 16:42 |
| 8 | PR extraction | CPRW | déplacement pur des blocs C&I/agricole — RWEB/AGC l'attendent (#1104 déjà en file) |
| 9 | PR | CPDF | PDF client C&I |
| 10 | PR | RGEN | vendeur résidentiel |
| 11 | PR | CPRS | devis web serveur |
| 12 | #1105 | RPDF | DÉJÀ en file (poussée sur instruction directe du fondateur, garanties Deye 5 ans / Dyness 10 ans) ; ses rounds suivants = commits sur jeton |
| 13 | PR | AGC | client agricole |
| 14 | PR | AGV | vendeur agricole |
| 15 | PR | RWEB | site / tunnel résidentiel |
| 16 | PR | RSIZ | R2 (RSIZ2-10) + R3 (postes_pret_devis_residentiel) — un seul jeton quand prêt |
| 17 | PR | CEC v4 | CEC18 (nan/inf refusés, 400 nommé), S3, sans urgence |
| 18 | PR | CE2E | recette finale |

Détenteur actuel : **RGEN #1103** (en file ; correctif goldens sous jeton). En vol : RPDF #1114, CQST #1097 (correctif stage-names), CORC #1115 — chacun re-fusionne main une fois à l’éjection. PRÉPA : CPRW r1. Suivant : CSV, CPDF, CPRS, CCAT r2+3 (stock 0175), AGC, AGV, RWEB, RSIZ, CEC v4, RPDF r2+3, CE2E.
