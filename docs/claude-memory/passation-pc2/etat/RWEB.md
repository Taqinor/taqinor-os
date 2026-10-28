ETAT: PR-OUVERTE #1131 (PRET-FILE, sans auto-merge — rouge stage-names corrigé par RWEB29, CI légère relancée)
BRANCHE: claude/pc2-rweb-3c86ec @ c97078a9a  PR: #1131
FAIT:
- 3 fusions de origin/main (dont #1129 AGC) ; conflits /professionnel ×3 + DONE LOG (deux côtés gardés).
- Page /proposition 11411 l. (main 11427) ; lib/proposition.ts 5400 (main 5436).
- RWEB27 : props C&I mortes retirées (+3 fonctions + test) ; préremplissage entreprise CPRW19 rendu serveur (vérifié
  maquette) ; impression #1104 : `.btn-pill` local rétabli ; `.cine-card` sur BandeauAvenant gardé (correction) ;
  commentaire PV80 « à confirmer fondateur » hors HTML client ; puce m³/jour agricole avec AGR_LBL_AGQ.eauJourEstimation.
- RWEB28 (Fable n° 3) : FAQ service FR/EN/AR sans « à confirmer » / « validation du fondateur ».
- roi_*_jamais : clés du contrat = page. CQST : rien de résidentiel nouveau.
- Contrôles : tsc OK ; astro build OK (avant correctifs texte + appel AGC) ; vitest un fichier à la fois verts ;
  check_forme_code/ownership/stages/codemap/api_shapes OK. check-astro-types OK (0 dépassement, 100 gelées connues).
RESTE: RWEB24 (payload de taille net, offres_tailles.py:1022). Suite proposée : ~80 commentaires HTML de la page en view-source.
ATTEND: JETON CI (la coordinatrice arme #1131)
DECISIONS: /professionnel Collectivités = texte CPRW sans chiffre ; entretien FAQ « communiqué sur demande ».
- RWEB29 : CI stage-names rouge (duplicata littéral) → RWEB17 annulée (tunnel = main), tableau garanties /garanties+/équipement en une source (lib/warranty.ts). ci_guards stage-names local RC=0.
