ETAT: MERGED #1120 (commit de merge 325bebfca, 28/10 ~03 h UTC)
BRANCHE: claude/pc2-agv-7541c6 @ d4fba5894  PR: #1120
FAIT: AGV1-11, 13, 14 cochées (AGV12 sans objet). main fusionné 28/10 (43e0c4fdd, PR #1118) : conflits = 2 plans
 (PLAN_AUDIT_DEVIS, PLAN_AUDIT_LEAD : groupe AIC de main + groupe AGV gardés tous deux). Migration crm 0144 toujours
 seule feuille (main s'arrête à 0143) → aucune renumérotation. main n'a touché AUCUN fichier AGV ni frontend/ →
 goldens générateur inchangés attendus ; pas de nouvelle critique Fable (logique agricole inchangée, Fable R2 déjà rendue).
 Gardes hôte : flake8+py_compile (17 .py) OK, check_stages OK, codemap --check OK, check_ownership OK,
 check_forme_code --base origin/main OK, check_api_shapes OK, eslint (11 fichiers) OK.
 Goldens générateur (TZ=UTC, sans -u) : 21/21 — agricoles verts ; 2 goldens gestes RÉSIDENTIELS instables sous charge
 (appel dimensionner intermédiaire en plus) puis 11/11 relancés seuls → aucune recapture, aucun fichier golden modifié.
RESTE: (1) fenêtre Docker ~15 min : test-backend.ps1 -RestoreDb sur visites.test_agr412 + crm (commit 3e835e488
 visite_checklist jamais rejoué en base). (2) Jeton CI : push, PR, --auto --merge. (3) Après merge : rendu réel du
 parcours lead pompage → visite validée → devis auto.
CORRECTIF: frontend-static rouge = jumeau oublié d'AGV6 (DevisGeneratorDeuxOptimiseurs.test.mjs figeait « Les deux » en agricole) → aligné, 1 push.
 (Local Windows : 2 tests CIQ126 rouges par CRLF seulement, verts en CI.) watch-ci.ps1 bloqué par ExecutionPolicy ici → gh pr checks --watch.
RE-FUSION 3 : conflits PLAN_AUDIT_LEAD/TRANSVERSE (deux côtés gardés, un seul DONE LOG) + golden gestes-autofill-agricole
 (recapture -u -t agricole = version AGV inchangée : les ajouts RGEN étaient du vocabulaire batterie). Gardes vertes, node:test OK (hors 2 CIQ126 CRLF locaux).
ROUGE FILE (run 40613847564) : (1) vitest VisiteWizardPage — visiteHelpers.MESURES_SCHEMA sans pompe_actuelle_kw (jumeau AGV2) → 8c9c63b84 ;
 (2) shard 3 crm.tests_services_split_golden — 3 empreintes AST (AGV3/4/9) ; (3) shard 7 GET leads detail entrees_pompage.manquants (+2 champs AGV1/8)
 puis MaybeEncodingError → shard 7 avorté. Correctif 157a0d8dd : services_split_ast (re-haché hôte, 0 écart), modele__Lead +
 serialiseur__LeadSerializer (calculés hôte, autres surfaces identiques), GET_leads(_detail), services_split_scenario (+2 null × 175).
DOCKER (jeton rendu, LIBRE) : rejeu harnais -RestoreDb -Parallel 1 de 205 modules (crm/visites/ventes du shard 7 + tous les modules AGV) :
 2349 tests, seuls 4 rouges environnementaux (test_actions_devis_ont_appelant, test_parcours_pa3 : lisent des fichiers hors django_core, absents
 du conteneur). 9 modules à racine de dépôt exclus (aucun agricole). Piège : -Parallel 2 + --keepdb réutilise des clones test_erp_db_N périmés.
main re-fusionné (#1122, #1114, #1125) sans conflit ; gardes hôte vertes.
ATTEND: rien. RESTE (2e round sec, après migrate de la base de dev) : rendu réel lead pompage → visite point d'eau validée → devis auto (desktop + mobile). Jeton CI à passer.
DECISIONS: AGV5 (visite validée lève la garde) ; AGV8 (part fixe déclarée, jamais supposée 0) ; AGV9 (mode_pompe jamais écrit auto).
