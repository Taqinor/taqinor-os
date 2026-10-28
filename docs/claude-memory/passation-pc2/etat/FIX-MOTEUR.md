ETAT: PR-OUVERTE #1134 (sans auto-merge)
BRANCHE: pc2-fix-moteur @ 7a1ba5521e  PR: #1134
FAIT: A (option « avec », chemin composition : CEC1 gardée par regles_au_moins(devis, 3) ; test ciq120 rouge puis vert) ; B (montants.reinitialiser_regles branché sur request_started + task_prerun hors eager ; test montants rouge puis vert) ; C (builder.py à 3046 lignes, commentaire seul ; import regles_calcul en tête de etude_ci.py pour C20) ; CMP12 GATED + D-CMP-7 ouverte (PLAN_AUDIT_DEVIS.md) ; critique Fable rendue (0 défaut de correctness, 2 défauts de spec corrigés) ; main fusionné (31db84ca84) ; contrôles hôte verts (33 tests purs, ci_guards stage-names + backend-lint-fast rc=0, forme/placement/ownership/stages/fingerprint/decisions/cablage OK).
RESTE: CI complète (jobs lourds) sous JETON ; le passage etudier_ci → regles_2710 n'a pas d'assertion (test base de données non jouable sans pile).
ATTEND: JETON CI
DECISIONS: (prises pour le fondateur, à revoir) voir decisions-prises.txt (FIX-MOTEUR ×3)
