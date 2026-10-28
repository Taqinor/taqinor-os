# RWEB — état au 27/10/2026 ~22:35

Branche locale `claude/res-rweb` (worktree zealous-morse-b178c0), NON poussée — attend « JETON RWEB » (n° 15).
3 rounds L3 construits + 2 critiques Fable (constats corrigés). Contrôles locaux verts : tsc, astro check (0 dépassement),
astro build, check_forme_code (C20 OK), vitest des modules touchés.

## Ce qui change (apps/web uniquement)
- /proposition : « Non rentabilisé sur 25 ans » (libellé PDF) au lieu de « Rentabilisé en 25 ans » ; retour sur chaque carte
  d'option ; « Rentabilisé en » partout ; durées trilingues ; économie « calculée/estimée » comme le PDF ; chaîne de prix EN/AR
  du PDF ; incertitudes retirées (prix à confirmer, CO₂ source à préciser, « notre moteur », TVA « à confirmer »).
- C&I (constats CPRW) : option phare / case pré-cochée / économie = `synthese_ci.option_servie`.
- Garanties du site entier : Deye 5, Huawei 10, Dyness DL5.0C 7, Powerbox Pro 10 ; panneaux 12/30 seulement Canadian Solar
  (comme theme.py) ; bloc garanties de /proposition par marque posée (`lib/proposition/garanties.ts`).
- Refactors purs : `lib/estimatorConstants.ts` (tarifs, LFP), `scripts/tunnel/dom.ts` (utilitaires des 3 mon-toit).

## Pour les autres sessions
- RPDF : le PDF lit `garantie_mois` du catalogue → tant que #1105 n'est pas mergée, PDF (Dyness 10, Deye « 5 à 10 ») ≠ site.
  `i18n_labels.res_n_ans` : « N سنوات » même > 10 (la page met « سنة »).
- RSIZ / devis : RWEB24 ouvert — le gain net 25 ans (PDF) exige que le payload de changement de taille
  (`offres_tailles.py:1022`, `economies_cumulees_25_ans_mad` = brut) serve aussi le net.
- AGC : ton libellé `eauJourEstimation` n'est pas sur main ; dès qu'il y est, je pose l'appel d'une ligne dans la page.
- CQST : liste de champs résidentiels envoyée (ville sans GPS, batterie_souhaitee, tranche_onee, equipements 15).
- CPRS : `roi_s_jamais`/`roi_a_jamais` sont servis mais absents des `contract_samples/proposal_*.json` (PACT10) — à ajouter.
