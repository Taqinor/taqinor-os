# Blocs d'état des sessions PC1 (23:05-23:35 UTC, 27/10/2026) — collés tels quels

Toutes les branches ci-dessous sont vérifiées sur `origin` (`git ls-remote`) à 23:35 UTC. Les sessions PC1 des
lanes cédées ne touchent plus leur branche.

## Lanes cédées au PC2

### CSV (branche poussée par la coordinatrice : le garde-fou de la session a refusé son push)
SESSION: CSV
BRANCHES: claude/ci-csv @ 3110893e6 (28 commits au-dessus d'origin/main, arbre propre)
FAIT: Rien n'est coché (les preuves en direct manquent). Construits et commités : CSV1-7 script d'appel pro ;
CSV12-13 talon et heures pro ; CSV15-16 facture résidentielle sur 1 ou 2 mois, question de l'été ; CSV17-18 agricole,
HMT, 220/380 V, débit et heures de la pompe actuelle, jours au butane ; CSV8-10 et CSV14 visite C&I, phase recopiée
sur le lead, « Sur la fiche : … — Confirmer », libellés de câbles D-CMP-2, bouton « Préparer le devis révisé » (contrat
CORC) ; correctif du test flaky RelanceEtapeRow.refus_geste ; contrat API régénéré ; DONE LOG écrit (décisions prises
pour le fondateur, 3 appels Fable).
RESTE: (1) poussée — fait. (2) Avec « JETON DOCKER » : rejeu en direct. Leads démo résidentiel et agricole remplis par
le seul script, puis lead C&I 2232/2233 → visite mobile 390 px → feu vert → « Préparer le devis révisé ». Recette dans
notes/csv-notes.md (conteneur sans montage csv-django :8011 + VITE_API_URL=http://localhost:8011 npx vite --port 5173 ;
éteindre ensuite). (3) Puis CSV11 (acceptation), en écrivant docs/audits/acceptation/CSV/<date>-<sha9>.md, et cocher
[x] CSV1-18 dans docs/plans/PLAN_AUDIT_LEAD.md. (4) Sur « JETON CSV » : git fetch && git merge origin/main (garder
l'import visite_checklist_pompage d'AGV), contrôles locaux, UN push, gh pr create puis gh pr merge --auto --merge,
suivre la CI. (5) Quand AGV1 sera sur main : ajouter depense_electricite_pompe_mad_mois (pompe électrique) dans
ORDRE_AGRICOLE d'appelGuidance.js, ETAPES_AGRICOLES de panneau_appel.py et panneau_appel.json (demande d'AGV).
CONTRÔLES: flake8 --max-line-length=120 sur les .py modifiés OK ; eslint sur les fichiers front modifiés OK ;
check_stages, codemap_fingerprint --check, check_ownership, check_api_shapes OK ; SimpleTestCase Django (venv
C:\csvvenv + scratchpad csvrun_main.py) OK ; vitest PanneauScriptAppel, VisiteWizardPage, VisiteBureauEtudesPage :
122 OK ; node --test appelGuidance : 71 OK ; tests DB NON joués ; Fable pré-merge : GO.
ATTENTES: JETON DOCKER ; JETON CSV ; AGV1 sur main pour la question pompe électrique.
FICHIERS: backend/django_core/apps/crm/{panneau_appel.py, visites_retour_lead.py, contract_samples/panneau_appel.json,
golden/services_split_ast.json, golden/scission_crm_http/GET_leads_panneau-appel.json, tests_cad148/175/agr401…} ;
backend/django_core/apps/visites/{visite_checklist.py, selectors.py, contract_samples/visite_terrain.json} ;
frontend/src/features/crm/relances/{PanneauScriptAppel.jsx, appelGuidance.js + tests} ;
frontend/src/pages/visites/{visiteHelpers.js, VisiteMesuresForm.jsx, VisiteWizardPage.jsx, VisiteBureauEtudesPage.jsx +
tests} ; frontend/src/api/visitesApi.js ; docs/crm/messages_meryem.md ; docs/plans/PLAN_AUDIT_LEAD.md (Groupe CSV) ;
docs/api-contracts.md.
PIÈGES: les exemples de panneau_appel.json sont comparés à la sortie réelle : régénérer depuis la sortie, jamais à la
main ; parité CAD153 md ↔ js : pas de chiffres dans les consignes du md ; golden HTTP panneau-appel : json indent=1,
ensure_ascii=False, sort_keys=True ; toute modif de RETOUR_LEAD_CI change le sha de golden/services_split_ast.json ;
base de dev PC1 en retard d'une migration (crm_equipecommerciale.recoit_leads) : créer un lead renvoie 500 ; le montage
bind de docker se bloque (9p) : utiliser le conteneur sans montage ; les tests DB ne tournent qu'en CI ; décisions à
dire au fondateur : CSV16 « Non » copie la facture d'hiver dans l'été ; CSV14 vise le devis le plus récent du lead (409
du serveur si ce n'est pas un devis C&I) ; restes PC1 non supprimés : worktree csv-visite, worktree
agent-a48740e826b41e80c, branches claude/ci-csv-script, -script2, -visite (aucun travail unique).

### RSIZ
SESSION: RSIZ
BRANCHES: claude/res-rsiz @ 26d601ad0 (pushed, no PR) — base origin/main 8bf522f21 ; R1 already merged via #1091
(claude/res-rsiz-move, ignore) ; claude/res-rsiz-a is an abandoned empty branch (broken worktree rsiz-lane-a on PC1).
FAIT: RSIZ2 (the « with battery » option's hybrid must be served by a priced in-stock battery; else no « avec » +
warning) · RSIZ3 (never grid + hybrid in the same offer: fuse with nb_avec = nb_sans, else « sans » alone + warning) ·
RSIZ4 (composition warnings returned as `avertissements_composition`) · RSIZ7 (calepinage shading loss in EntreesMoteur
+ fingerprint + `entrees.kwargs_moteur_ombre`) · RSIZ8 (battery ladder bound = 2 000-panel sweep ceiling, 120 stays a
signal) · RSIZ9 (adaptive sweep refinement up to 3 passes, dense ≤ 60 unchanged) · RSIZ10 (`domain/taille.py` returns
`ResultatTaille`, a 4-tuple with `.hors_residentiel`) · RSIZ11 = R3 (`apps.ventes.selectors.postes_pret_devis_residentiel(company)`,
CCAT shape pret_devis_ci.json; CCAT told) · RSIZ5 WIP (DC cable from derived MPPT pairs, gated by
`paires_mppt_derivees` = rules level ≥ 3; last commit).
RESTE: (1) RSIZ5: finish the recapture of golden `tests/golden/split_dm_comp.json` (the lane was stopped mid-recapture:
check how test_composition_source_unique / the golden harness recaptures, rerun it, verify the diff only moves the
edited etape_composer symbols) and check that etape_composer really passes
`paires_mppt_derivees=regles_au_moins(devis, REGLES_CORRIGEES_2710)` · (2) RSIZ6: warning « phase supposée triphasée »
when phase unknown and tri ≥ 10 kW assumed (composition_residentielle.py, same `avertissements_composition` key) · (3)
write the v3 tasks RSIZ2-11 in the plans (PLAN_AUDIT_DEVIS.md for composition*/etape_composer/catalogue/pret_devis;
PLAN_AUDIT_MOTEUR.md for dimensionnement*/offres_tailles; multi-owner → PLAN_AUDIT_TRANSVERSE.md group RSIZ already
exists there with RSIZ1) + DONE LOG lines incl. « Décision prise pour le fondateur (à revoir) » · (4) validation by a
fresh agent, Fable critique pre-merge (+ DONE LOG line per Fable call) · (5) with JETON DOCKER: re-render the 8 real
auto quotes (company 156 anonymised snapshot, Casablanca terrasse béton, bills 500/1 500/6 000 mono+tri/25 000/80 000
tri + scenario avec/100 000 tri) via `docker cp` probe + `docker exec … manage.py shell` in transaction.atomic +
set_rollback (PC2 rewrites the probe), then run the touched test modules: `powershell -File scripts/test-backend.ps1
-RestoreDb -Modules "apps.ventes.tests.test_pvkit_composition apps.ventes.tests.test_deux_optimiseurs
apps.ventes.tests.test_composition_source_unique apps.ventes.tests.test_t5_dimensionnement_devis
apps.ventes.tests.test_qjr_cout_balayage apps.ventes.tests.test_qjr411_plafond_message_honnete
apps.ventes.tests.test_qjr_entrees_moteur"` · (6) list moved residential golden hashes under
golden/moteur/build_quote_data/ and warn RPDF · (7) on JETON RSIZ: ONE PR, `gh pr merge --auto --merge`, own CI. NO
TEST AGAINST A REAL DATABASE HAS RUN for RSIZ2-11.
CONTRÔLES: on every commit `flake8 --select=E9,F,W6` + `py_compile` clean; `python scripts/check_forme_code.py --base
origin/main` OK at 514e96eec (WIP diff also checked); `python scripts/check_ownership.py` OK. Lane B ran the pure
balayage_adaptatif logic on a toy sweep. Not run: codemap_fingerprint --check, check_stages, any Django test.
ATTENTES: JETON DOCKER (re-render 8 quotes ~20 min + touched test modules) · JETON RSIZ (one PR) · RHOR (archivée) :
add `perte_ombrage_pct` to `balayer_stockage_horaire` — until then shading stays OFF by design · owner of
`apps/ventes/domain/etudes.py` (~l.506): pass `perte_ombrage_pct=entrees['perte_ombrage_pct']` to recommander_taille
once that lands · RGEN: copy `avertissements_composition` into etude_params and show `ResultatTaille.hors_residentiel`.
FICHIERS: apps/ventes/{dimensionnement.py (must not grow), dimensionnement_balayage.py, balayage_adaptatif.py,
offres_tailles.py, etape_composer.py, selectors.py (1 998 lines — do not grow further)} ;
apps/ventes/domain/{composition.py, composition_residentielle.py, catalogue.py, lignes.py, entrees.py, taille.py,
dimensionnement_devis.py, pret_devis_residentiel.py (new)} ; tests test_pvkit_composition, test_deux_optimiseurs,
test_composition_source_unique, test_t5_dimensionnement_devis, test_qjr_cout_balayage,
test_qjr411_plafond_message_honnete, test_qjr_entrees_moteur, golden split_dm_comp.json.
PIÈGES: never `git worktree add` on the PC1 disk · a killed agent leaves a stale `.git/worktrees/<wt>/index.lock` ·
flake8 CI = E9,F,W6 only · frozen exports (dimensionnement.HORIZON_MARGINAL_PV, depart_dans_horizon,
point_depart_meilleur_payback, ratio_pas_marginal; horaire.conso RATIO_*; quote_engine/pricing constants) · sent quotes
keep their figures: every behaviour change gated by `regles_au_moins(devis, REGLES_CORRIGEES_2710)` · Deye 5 kW Isc
22 A is a founder decision (24/08), never touch · ladder MAX_SONDES_ECHELLE = 24 may cap probes on huge profiles · QJR112
worst-case note (237 sizes) now understates RSIZ9's extra passes, outside RSIZ files · decisions taken for the founder
(to review): shading only when all engines accept it; hors_residentiel as an attribute on a 4-tuple; readiness:
three-phase/alu/smart meter/wifi optional, battery mandatory, inverter with incomplete sheet = to complete;
protections = the single `tableau` role.

### AGC
SESSION: AGC
BRANCHES: claude/agr-agc @ 61faa0a7b (poussée, sans PR)
FAIT: 13 tâches cochées, 8 commits sur origin/main 90218a848. AMOT65 (moitié rendu) : « estimation » suit
`production.etiquettes` du noyau. AGC1 : « rendement non publié… borne haute » ne sort plus au client. AGC2 : cartes
pompage de la une-page déplacées dans `quote_engine/agricole/onepage.py` ; `generate_devis_premium._cartes_pompage_synthese`
y délègue ; plus de « (hypothèse) ». AGC9 : la synthèse dit « pompe existante » et sert la plaque. AGC11 : bloc argent
non publiable mais dépense déclarée → ligne neutre « Votre dépense actuelle déclarée : X MAD par an… », libellés dans
`quote_engine/i18n_labels_agricole.py` consulté d'abord par `pages._t`. AGC12 : `VIDE_MAX_MM` 95→45, plus de double
respiration en page 1, carte eau courte. AGC13 : « HMT » traduit sur la une-page. Site (WEB_PLAN, Groupe AGC) : AGC4-6
/pompage-solaire FR/EN/AR, TVA sur la pompe seule, coût « réduit » au lieu de « zéro », plus aucun « comme nos
toitures » ; AGC7 formule du m³ sur l'horizon servi ; AGC8 « estimation » suit `eau.estimation`, nouveau libellé
`eauJourEstimation` ; AGC10 aria-label traduits, dt avant dd, viewBox 260→272.
RESTE: (a) résultat de la vérif R3 (agent opus, lecture seule) pas rendu — le PC2 la refait : relecture de `git diff
origin/main...HEAD` contre les tests qui portent les anciens littéraux. (b) AGC14 (ouverte) : même ligne neutre côté
/proposition — contrat d'abord, clé `depense_declaree` dans les deux `proposal_data.json` (backend + copie web). (c)
Tests Django des modules touchés, dans le conteneur : `docker compose -p erp-agentique run --rm --no-deps -T -e
AGC_MODS=test_agr302_onepage_agricole_formats,test_agr304_synthese_agricole,test_agr313_onepage_lit_synthese,test_agr310_renderer_agricole,test_agr314_agricole_langues,test_quote_engine_amot37_pages_agricole,test_agr317_vocabulaire_agricole,test_agr305_garanties_pompage,test_agr306_mentions_agricoles,test_agr307_synthese_economies
django_core python manage.py shell -c "exec(open('_agc_tests.py').read())" < /dev/null` — `_agc_tests.py` (unittest
sans base) était hors git dans le worktree PC1 : à réécrire ; `test_quote_engine_formats` (TestCase) non couvert. (d)
Rendu réel R2 : `_agc_rendu.py` (idem, à réécrire), `-e AGM_TEST_PRIX=1 -e AGC_REGLAGES=1 -e ROUND=r2`, PDF dans
`_agc_out/<round>/`, lire chaque page. (e) Goldens à recapturer APRÈS le merge de #1114 RPDF : `merge origin/main`, puis
`docker compose run --rm --no-deps -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev -e UPDATE_GOLDEN=1 django_core
python manage.py test apps.ventes.tests.test_moteur_golden_legacy apps.ventes.tests.test_moteur_golden_build_quote_data` ;
ne garder que `legacy/onepage_agricole.json` et `build_quote_data/agricole__*`. (f) Fable R4 (œil client) + critique
Fable pré-merge, round 3 L3 complet, jusqu'à 2 rounds secs. (g) Une seule PR au jeton CI.
CONTRÔLES: 116 tests sans base OK dans le conteneur avant les commits R2 ; tests de R2 (AGC11-13, formats) NON lancés ;
vitest web 97/101 (4 délais 5 s propositionOptionAGW308, code non touché) ; flake8, check_forme_code, codemap --check,
check_stages OK ; `npm run check` (tsc) > 20 min (124) NON vérifié ; `astro build` + `pompageTvaAGW305` NON lancés.
ATTENTES: Docker ; merge de #1114 avant les goldens ; jeton CI ; RWEB (puce `eau_m3_jour` de `[...token].astro:2527` →
`eauJourEstimation`) ; CCAT (description de `VEI-SI22-AFF`) ; RPDF (repli de `legacy_onepage.py:190-220`).
FICHIERS: `quote_engine/agricole/*`, `quote_engine/i18n_labels_agricole.py` (neuf), `utils/garanties.py`,
`apps/web/src/lib/{propositionAgricole,estimatorAgricole,agronomy}.ts`, `pages/{,en/,ar/}pompage-solaire.astro`,
`components/CarteAideEtat.astro`, `components/proposition/agricole/**`, section pompage de `lib/serviceFaq.ts`.
PIÈGES: `i18n_labels.py` et `generate_devis_premium.py` : aucune croissance ; `test_quote_engine_formats.py` > 2 000
lignes : +0 ligne logique ; le devis auto agricole ne persiste pas `mode_pompe` ; catalogue anonymisé : 3 CV/50 m et
30 CV/100 m refusés « aucune pompe chiffrable » (ne rien inventer) ; rendu fidèle = `registre_renderers()` ; le devis
imprime 20 % de TVA sur la pompe alors que le site la dit exonérée : TVA du kit = manuel (D8), signalé, pas touché ;
décisions D-AGC-1 à D-AGC-7 dans `PLAN_AUDIT_MOTEUR.md` et `WEB_PLAN.md` ; note : notes/AGC-r1-constats.md.

**Complément AGC (23:50 UTC, vérification indépendante du round 3 rentrée après le push — 5 constats à corriger AVANT la PR, détail dans `notes/AGC-r3-validation-pour-PC2.md`) :** (1) le golden `legacy/onepage_agricole.json` bouge (tag pdf : sauté en CI de PR, rouge en release-verify) → le recapturer ; (2) `_depense_declaree` imprime « déclarée » sur des mois pré-cochés non confirmés (`MOTIF_MOIS_CALENDRIER`) → ne rien imprimer dans ce cas ; (3) la phrase « chiffrée après la visite » est fausse quand le motif est le barème des charges non saisi → la retirer ; (4) la formule web du coût du m³ omet les remplacements → ne l'afficher que pour un nouveau forage ; (5) AGC9 peut dire « pompe existante » sur un devis de pompe neuve saisi à la main → AGM doit persister `mode_pompe` dans `entrees_pompage`, sinon restreindre la règle. Aucun autre test cassé vu par le validateur.

### AGV
SESSION: AGV
BRANCHES: claude/agr-agv @ 7b545201b (poussée, vérifiée)
FAIT: AGV1-AGV11, AGV13, AGV14 cochées ; AGV12 sans objet (PLAN_AUDIT_LEAD : AGV1-5, AGV9 ; PLAN_AUDIT_GENERATEUR :
AGV7, 10, 12, 13 ; PLAN_AUDIT_DEVIS : AGV14 ; PLAN_AUDIT_TRANSVERSE : AGV6, 8, 11). Migration crm
0144_agv1_depense_electricite_pompe (2 colonnes Lead ; dépend de 0143_equipecommerciale_departement). Visite point
d'eau déplacée dans visites/visite_checklist_pompage.py (+ mesure pompe_actuelle_kw). Retour visite → lead : plaque kW,
tension 220/380 et phases ; mesure non recopiable nommée au chatter. Garde D-AGR-4 levée après une visite VALIDÉE.
Générateur agricole sans vocabulaire batterie (scénario Sans par défaut, rail « Total TTC »). PanneauAgricole sans
jargon ; carte économie cumul 10 ans servi par le serveur. Facture électricité + part fixe → facture_reseau. Tension de
plaque à source unique. main fusionné le 27/10 vers 22 h (c53582bd9).
RESTE: (1) re-fusionner main ; si une autre PR a pris crm 0144 : renuméroter la mienne et la re-chaîner. (2) Gardes :
check_stages, codemap_fingerprint --check, check_forme_code --base origin/main, check_ownership. (3) Recapture des
goldens générateur agricoles si main a bougé : `cd frontend ; TZ=UTC npx vitest run
src/pages/ventes/DevisGeneratorGolden.test.jsx src/pages/ventes/DevisGeneratorGoldenGestes.test.jsx -u -t agricole`
(seuls f-agricole-pompe-courbe.html et gestes-autofill-agricole.txt doivent bouger). (4) Au jeton CI : PR → main,
`gh pr merge --auto --merge`. (5) Après merge et migrate de la base de dev : rendu réel du parcours lead pompage →
visite point d'eau validée → devis auto (desktop + mobile) = 2e round sec.
CONTRÔLES: test-backend.ps1 -RestoreDb -Parallel 1 sur 7 modules (crm.tests_agr400/404/413, tests_devis_auto,
visites.test_agr412, ventes.test_agr_economie_pompage, test_agr121) → 211 OK ; un commit visites ensuite non rejoué
(flake8 OK) ; gardes OK ; check_api_shapes OK ; node --test sizingReducer 45/45 ; vitest SectionsRender 85/85,
PanneauAgricole 25/25, RailArgent 5/5, goldens 21/21 (TZ=UTC).
ATTENTES: jeton CI ; rendu réel après merge ; CQST8 et CSV attendent AGV1 sur main ; RPDF bouge agricole__* → AGC.
Décisions prises pour le fondateur (à revoir) : AGV5 (visite validée lève la garde) ; AGV8 (part fixe déclarée, jamais
supposée 0) ; AGV9 (mode_pompe jamais écrit automatiquement, note seulement).
FICHIERS: models_lead_pompage.py, visite_checklist_pompage.py (neuf), PanneauAgricole.jsx, CarteEconomiePompage*.jsx,
economiePompagePreviewPur.js, goldens générateur agricoles. Touches hors propriétaire acceptées : visite_checklist.py
(import du module pompage) ; crm/devis_auto.py (garde AGV5) ; SectionEnergie.jsx, fieldLabels.js, draftCore.js (2 champs
pompage) ; DevisGenerator.jsx (0 ligne nette, 2311) ; RailArgent.jsx, sizingReducer.js ; crm/visites_retour_lead.py,
devis_selectors.py, activity.py, fiche_selectors.py ; ventes/domain/pompage.py, ventes/economie_pompage.py ; contrats
lead_pompage.json et visite_terrain.json.
PIÈGES: goldens générateur : TZ=UTC obligatoire, `-t agricole` ; check_forme_code refuse toute ré-export de nom ;
check_ownership : tâche multi-propriétaires → PLAN_AUDIT_TRANSVERSE ; golden f : select Scénario masqué montre « Les
deux » mais le payload envoie « Sans batterie » ; fichiers CRLF : écrire en LF.

### CPRS
SESSION: CPRS
BRANCHES: claude/ci-cprs @ eb9da2c81 (poussée, 9 commits au-dessus de main, aucune PR)
FAIT: CPRS1-11 tous cochés dans docs/plans/PLAN_AUDIT_DEVIS.md. /proposition sert les chiffres de l'option servie
(C&I) = PDF ; libellés/étude internes retirés ; textes C&I+agricole traduits par les fonctions du PDF (payload_ci.py) ;
kit agrégé au niveau standard ; notif « devis ouvert » fiable (+ devis sans lead → auteur, CPRS9) ; signature : offre
1 option signable seulement sur elle, option non offerte/non chiffrée jamais signable, ICE canonique ; libellé O&M
déséchappé (CPRS11) ; contrat proposal_data.json (2 copies identiques) avec exemple C&I 2 options réel ; golden
split_pv_comportement recapturé ; acceptation CPRS10 enregistrée docs/audits/acceptation/CPRS/2026-10-27-9de01bcb8.md
(parité page/PDF 0 écart : C&I 6 leads, résidentiel 3, agricole 3). 1 critique Fable (R1), suites appliquées.
RESTE: (1) lignes DONE LOG (CPRS9-11 + ligne Fable R1) dans PLAN_AUDIT_DEVIS.md ; (2) au jeton : merge origin/main,
contrôles hôte (flake8, check_stages, codemap --check, check_api_shapes, check_forme_code --base origin/main) ; (3) UN
push, `gh pr create` (corps : décisions « prises pour le fondateur (à revoir) » + golden data_* changés),
`gh pr merge --auto --merge`.
CONTRÔLES: harness docker 16 modules ventes/portail/sav + split_pv_comportement → 182 tests OK ; check_api_shapes OK ;
flake8 OK. Pas refaits après merge de main.
ATTENTES: jeton CI ; pas de Docker nécessaire ; aucune décision bloquante.
FICHIERS: backend/django_core/apps/ventes/public/* (payload_ci.py nouveau, lecture_views, signature_views…),
apps/ventes/contract_samples/proposal_data.json + apps/web/src/contract_samples/proposal_data.json (JSON-égaux), tests
ventes CPRS (dont test_ciq306_synthese_ci_servie.py), golden split_pv_comportement.json, groupe CPRS de
PLAN_AUDIT_DEVIS.md, docs/audits/acceptation/CPRS/. public_views.py : lecture seule sauf l'appel d'une ligne.
PIÈGES: NE JAMAIS committer backend/django_core/_cprs_*.py ni _cprs_out/ (données réelles anonymisées, PC1 seulement) ;
public_views.py ≥ 2 000 lignes : 0 ligne nette ; si un test touche la charge utile publique, le golden
split_pv_comportement change → recapture `SPLIT_GOLDEN_CAPTURE=1` (TestCase, DB) ; `economie_annuelle_mad` de
option_batterie = économie TOTALE HT de l'option ; pas de clé postes_hors_total.

### RWEB (branche poussée par la coordinatrice : le garde-fou de la session a refusé son push)
SESSION: RWEB
BRANCHES: claude/res-rweb @ 4852b2839 (12 commits sur origin/main 90218a848)
FAIT: RWEB1-7, RWEB9, RWEB11-23, RWEB25, RWEB26 cochés (docs/WEB_PLAN.md, Groupe RWEB + DONE LOG). /proposition :
« Non rentabilisé sur 25 ans » via roi_*_jamais ; retour par carte d'option ; « Rentabilisé en » partout ; durées
trilingues (lib/proposition/retour.ts) ; économie calculée/estimée selon savings_model_* ; chaîne de prix EN/AR =
i18n_labels ; incertitudes retirées ; erreurs de signature EN/AR (lib/proposition/messagesSignature.ts) ; C&I : option
phare/économie = synthese_ci.option_servie. Garanties sur tout le site : Deye 5, Huawei 10, Dyness DL5.0C 7, Powerbox
Pro 10 ; panneaux 12/30 seulement Canadian Solar — lib/warranty.ts + lib/proposition/garanties.ts. Refactors purs :
lib/estimatorConstants.ts, scripts/tunnel/dom.ts. 2 appels Fable, 6 constats corrigés.
RESTE: (1) poussée — fait ; (2) au JETON RWEB : merge origin/main (conflits possibles sur
apps/web/src/pages/proposition/[...token].astro ou lib/proposition.ts — fichiers ≥ 2 000 l., aucune croissance nette :
wc -l + check_forme_code --base origin/main), `gh pr create` + `gh pr merge --auto --merge` ; (3) RWEB24 ouvert (gain
net 25 ans comme le PDF) — attend que le payload de changement de taille (offres_tailles.py:1022) serve le net ; (4)
rounds secs ; (5) appels d'une ligne : libellé AGR_LBL_AGQ.eauJourEstimation d'AGC dans la puce eau_m3_jour du héros,
contrat CQST (#1097) si de nouveaux champs résidentiels arrivent ; (6) régression CSS impression de #1104 (CPRW) : NON
examinée par RWEB — voir CPRW / audit Fable #3.
CONTRÔLES: npx tsc -p tsconfig.check.json OK ; node scripts/check-astro-types.mjs OK ; npx astro build OK ;
check_forme_code C20 OK ; vitest des modules touchés verts (≈ 1 400). Suite complète vitest : échecs environnementaux
seulement (maplibre-gl.css via jonction, dist/client, timeouts proxys, estimatorBrainV7 lent).
ATTENTES: jeton CI ; #1105 (RPDF) mergée ; contrat CQST ; libellé AGC. Aucun Docker requis.
FICHIERS: apps/web/src/pages/proposition/[...token].astro, apps/web/src/lib/proposition.ts,
apps/web/src/lib/proposition/{retour,garanties,messagesSignature}.ts, components/proposition/ChainePrix.astro,
lib/{warranty,fiches,estimatorConstants,estimatorBrainV2,batterySim,billEstimate,lead}.ts, lib/tunnel/champs.ts,
scripts/tunnel/dom.ts, pages/{,en/,ar/}devis/mon-toit.astro, pages garanties/équipement/faq/batteries-stockage/guides
batterie/pourquoi-taqinor/professionnel, tests/{warranty,propositionAgricoleAGW300,propositionSyntheseCiCIW300,…}.test.ts.
PIÈGES: PAGE et proposition.ts : aucune croissance nette ; les tests lisent la source en texte : tout renommage casse des
tests ; un span `data-i18n` est remplacé par un triplet fr/en/ar au chargement : passer par
window.__propRegisterBusyLabel ; vérifier `grep -rl $'\x08' apps/web/src` après toute édition générée ; maquette de
rendu : mock/serveur.mjs (node, :8799) + PUBLIC_API_BASE=http://localhost:8799 npx astro dev --port 4391 ; note :
notes/RWEB-etat.md.

### CEC v4
SESSION: CEC
BRANCHES: claude/ci-cec-v4 @ b7f0bb76a (poussée, sans PR)
FAIT: mergé sur main — #1082 (CEC1-5, CEC7-9) et #1096 (CEC10-14, CEC16-17). v4 porte CEC18 (S3) : prix déclaré non
fini (nan/inf/1e400) refusé dans tarif_ci._num ; POST economie-ci/preview/ : sortie_etude_ci hors contrat → 400
{champ: sortie_etude_ci}, journalisé ; motif exact pour un contrat bt_domestique ; CEC19 ouverte (bande de
vraisemblance d'un prix déclaré = DÉCISION fondateur, non construite). Rounds R8-R10 secs/non secs, R11 coupé par le
crash.
RESTE: (1) merge origin/main (conflit attendu seulement dans PLAN_AUDIT_DEVIS.md DONE LOG : garder les deux côtés) ;
(2) contrôles hôte ; (3) à « JETON CEC » : un push, gh pr create, gh pr merge --auto --merge ; (4) suivre jusqu'à
MERGED ; (5) round 11 (intégration, lecture seule) puis un dernier round pour 2 secs consécutifs ; (6) CEC6
(acceptation en direct) = orchestrateur avec pile + JETON DOCKER.
CONTRÔLES: flake8 (fichiers touchés) OK ; tests purs hôte test_ciq203/204/206/207/208/209/231/233 : 121 OK sauf
test_cec7 (modèles, vert en CI) ; check_forme_code, check_test_placement, check_taches_cablage, check_ancres_taches,
check_decisions OK. Critique Fable pré-push : PUSHABLE.
ATTENTES: JETON CI. Aucun docker.
FICHIERS: apps/ventes/{economie_ci.py (≥ 2 000 l., aucune croissance nette), tarif_ci.py, economie_ci_options.py,
economie_ci_view.py}, apps/ventes/domain/conditions_ci.py ; tests test_ciq203/204/206/207/208/209/231/233,
test_ciq210_branchement.py, test_adev28 ; groupe CEC de PLAN_AUDIT_DEVIS.md.
PIÈGES: (a) toute correction de chiffre se branche sur regles_au_moins(devis, 3), JAMAIS calcul_corrige ; le tarif d'un
devis envoyé porte regles_origine:True. (b) Point #1094 (CMP, hors surface CEC) : apps/ventes/domain/etude_ci_batterie.py:425
appelle investissement_hors_om(…, calcul_corrige(devis)) → l'O&M sort de l'an 0 de l'option avec dès le niveau 2
(devis envoyés 08-27/10) ; doit être `regles_au_moins(devis, REGLES_CORRIGEES_2710)` ; vérifier aussi l.237 — CMP
archivée : à traiter par la coordinatrice PC2 (audit Fable final) ou CEC v4. (c) economie_ci.py ≥ 2 000 lignes. (d)
CRLF Windows : éditer avec l'outil Edit. (e) test_cec7 échoue toujours sur l'hôte. (f) attendre la fin de TOUS les
shards avant un push correctif.

### CCAT rounds 2+3
SESSION: CCAT
BRANCHES: claude/ci-ccat-r3 @ c54b9c0b0 (à reprendre : r2 + r3, à jour de main au 27/10 ~22h UTC) ; claude/ci-ccat-r2 @
1e2b6c53a (ancêtre, sauvegarde seulement)
FAIT: vague 1 mergée (#1081). Sur r3 : CCAT8 tableau `GET /api/django/stock/produits/pret-devis-ci/`
(apps/stock/pret_devis_ci.py), CCAT9 encadré /stock + `?ci=a_completer`, CCAT10 semis protection DC/parafoudres/terre/
structures des 6 poses à prix vide + câbles AC Nexans (management/commands/_articles_ci.py), CCAT11 panneau sans
Pmax/prix visible, CCAT12 bouton « Compléter », CCAT13 tableau agricole `GET …/pret-devis-agricole/`
(apps/stock/pret_devis_agricole.py), CCAT14 encadré à onglets C&I/Agricole, CCAT15 fiche Deye sans « SUN-…SG »
(seed_catalogue._PREMIERE_LIGNE_DEYE) + migration stock 0175_ccat15_description_hybrides_deye (texte semé exact,
réversible), CCAT102 compteur Paramètres, CCAT103 prestations C&I en tableau. Contrats :
stock/contract_samples/pret_devis_ci.json, pret_devis_agricole.json, produit_ci.json.
RESTE: (1) lire la critique Fable pré-merge r2+r3 (lancée ~23h, non rendue au push) et corriger ses bloquants — le PC2
la relance ; (2) au jeton : merge origin/main (CODEMAP en conflit → garder les deux côtés puis
`PYTHONIOENCODING=utf-8 python scripts/codemap_fingerprint.py --write`), contrôles, `gh pr create --base main --head
claude/ci-ccat-r3`, `gh pr merge <n> --auto --merge` ; (3) CCAT16 APRÈS le merge de RSIZ : route `pret-devis-residentiel`
appelant `apps.ventes.selectors.postes_pret_devis_residentiel(company)` (commit RSIZ 514e96eec) + 1 ligne dans
`SEGMENTS` de frontend/src/pages/stock/PretDevisCi.jsx ; (4) optionnel : filtre « type de pompe ».
CONTRÔLES: flake8 120 + py_compile OK, lint-imports 21/21, check_api_shapes, check_ancres_taches, check_taches_cablage,
check_forme_code, check_filtre_chemins_ci, codemap --check OK, eslint propre, vitest stock+paramètres verts. Tests
Django NON joués en local. Revues R3 opus : 2 défauts corrigés. Fable R4 round 1 + pré-merge round 1 rendus ; pré-merge
r2+r3 NON rendue.
ATTENTES: jeton CI ; merge de RSIZ pour CCAT16.
FICHIERS: apps/stock/{selectors.py::produits_ci, etat_ci.py, pret_devis_ci.py, pret_devis_agricole.py,
views/produit.py, serializers.py::get_etat_ci, contract_samples/*, management/commands/{seed_catalogue.py,
_articles_ci.py}, migrations/0175_ccat15_*, test_ciq101/102/103*, test_astk_seed_additif.py}, core/product_roles.py,
frontend/src/features/stock/{catalogue.js, libellesProduitCi.js}, frontend/src/pages/stock/{PretDevisCi.jsx,
CatalogueTable.jsx, ProduitDetail.jsx, ProduitForm.jsx, StockList.jsx}, frontend/src/api/stockApi.js,
frontend/src/pages/parametres/{DevisSection.jsx, PrestationsCiTable.jsx, peConstants.js, ParametresEntreprise.jsx}.
PIÈGES: migration stock 0175 : re-vérifier contre main au push (`git ls-tree --name-only origin/main
backend/django_core/apps/stock/migrations/ | tail -3`) ; si une autre 0175 existe → `makemigrations stock --merge`,
jamais renuméroter une migration de main ; Produit : contrainte unique (company, nom) — noms distincts par test ; un
test frontend ne lit aucun fichier backend hors contract_samples (check_filtre_chemins_ci) ; pas de « miroir de » en
prose (PACT159) ; clauses v3 + ancres `fichier::symbole` sinon stage-names rouge ; jamais `git checkout origin/main -- .` ;
ProduitForm.jsx, selectors.py, serializers.py : aucune croissance nette.

**Complément CCAT (23:55 UTC, critique Fable pré-merge r2+r3 rendue après la passation — 5 bloquants à corriger par le PC2 avant le push de claude/ci-ccat-r3, détail dans `notes/CCAT-fable-r2r3-bloquants.md`) :** (1) `check_api_shapes.py --write` (docs/api-contracts.md en retard → stage-names rouge) ; (2) `?ci=a_completer` lu seulement à l'init → bouton de l'encadré sans effet depuis /stock ; (3) postes agricoles renvoient au filtre C&I au lieu du filtre pompage ; (4) pompe sans type « immergée » dite ok alors que le moteur la refuse ; (5) migration 0175 ne couvre pas l'ancienne variante du texte Deye (12/06) → filtre sur le préfixe « Onduleur hybride Deye SUN-…SG ».

### CE2E
SESSION: CE2E
BRANCHES: claude/beautiful-shannon-68c69b @ 38ec7d962 (= main de PR #1070, AUCUN commit propre) → PC2 repart de
`origin/main`.
FAIT: rien (aucun scénario, spec, note ni enregistrement).
RESTE: toute la recette. Au départ sur PC2 : `git fetch && git checkout -b ce2e origin/main` ; lire le bloc commun +
section CE2E de docs/ci-l3-sessions.md et docs/res-agr-l3-sessions.md ; pile locale à jour (`docker compose up -d
--build`, `manage.py migrate`, rebuild front, `seed_catalogue`) ; jouer 10 profils C&I (dont boulangerie lead 1637) + 4
résidentiels + 2 pompage via le générateur /ventes/devis/nouveau → /proposal ; relecture Fable de chaque sortie ;
preuves en direct RHOR8, AMOT64, CLD9, CLD13 ; enregistrements docs/audits/acceptation/<G>/<date>-<sha9>.md ;
corrections routées au propriétaire du fichier ; une PR par vague.
ATTENTES: merges amont de TOUTES les sessions L3 avant de jouer.
PIÈGES: MCP playwright/chrome-devtools/serena avaient échoué à se connecter au démarrage sur PC1 — vérifier /mcp sur
PC2 ; aucune écriture prod, aucun deploy.

## Lanes PC1 (restent sur PC1 jusqu'à son plafond ; si PC1 s'arrête avant, reprendre ici)

### RPDF
- #1114 = claude/res-rpdf-r1 : en LOCAL (non poussé) porte désormais R1+R2+R3 (fusion de claude/res-rpdf-r2r3 ; contrôles hôte verts : flake8, check_forme_code avec budgets C20 déclarés au plan, check_test_placement, check_money_rounding, codemap --check). Sur origin encore @ 089f6956e (éjectée 2× : goldens). Sauvegarde claude/res-rpdf-r2r3 @ 9ff5e03b9 (R1 + R2
  RPDF11-24 + R3 RPDF30 formats EN ; R2/R3 jamais joués en Docker).
- Décision coordinatrice 23:35 : R2+R3 entrent DANS #1114 (une seule recapture, une seule CI) : après le merge de
  #1115, fusionner main, JETON DOCKER, recapturer les 125 goldens + rejouer les 8 modules, UN push, `gh pr merge 1114
  --auto --merge`.
### CORC
- #1115 = claude/ci-corc-v2 @ 79828101c, en file, UNMERGEABLE derrière #1113 (fondateur). Rien de local. Au merge de
  #1113 : si éjectée → merge main une fois, vérifier goldens, UN push, re-armer. Vague 3 / CORC11 non commencées.
### RGEN
- #1103 = claude/res-rgen @ 5387520cc, en file pos 4 UNMERGEABLE. Rien de local (sauf axios.js délai local, jamais
  poussé). Même consigne au merge des entrées devant (2 goldens SPL312 + gestes à revérifier).
### CQST
- #1097 = claude/ci-cqst @ e172855c0 (e72130416 + ancre CQST8), sur main 71abb6b7d ; auto-merge armé ; gardes locales passées (check_taches_cablage, ancres, duplicats, acceptation, ownership, build_order, stages, CODEMAP, api_shapes, forme_code, tsc/astro apps/web, vitest questionnaire 249/249). CI du run en cours ; la file la reconstruit.
### CPRW
- #1116 = claude/cprw-r1, en file. Round 2 → sauvegarde claude/cprw-r2 @ b818e04a6 (CPRW15 garanties C&I servies, CPRW16 échéancier servi, CPRW17 services O&M/suivi/raccordement, CPRW18 comparaison sans/avec batterie servie, CPRW19 préremplissage ICE, CPRW23 postes « à chiffrer après visite » lus dans a_confirmer). Reste : CPRW20 (/professionnel « onduleurs 10 ans » non dérivé, CTA par segment), CPRW21 (définitions autoconso/couverture FR/EN/AR + parité), CPRW22 (tableau jalons mobile, ordre des pilules), fusion du round 1, relecture Fable, rendu réel, lignes WEB_PLAN ; non relu, pas de PR.
### CPDF
SESSION: CPDF — BRANCHES: claude/cpdf @ bd7e165ae (poussée, sans PR ; 28 fichiers, +1492/−225 vs main ; worktree sharp-cartwright-8e73c2).
FAIT: CPDF1-10 codés et commités : l'option batterie imprime SES chiffres/échéancier/payback (valeur servie, jamais le quotient) ; deux cartes d'option en couverture (nouveau ci/options_cote.py) ; deux cases d'option sur le bon pour accord ; plus de jargon ni d'incertitude (scénario prudent, TVA non déclarée, (moteur C&I), IEA/NREL/P50/P90, ≈, TVA 18 %, « calculation method » EN/AR) ; payback à une décimale calculé UNE fois dans chiffres_cles (parité PDF = /proposition) ; nom du client une fois dans sa casse, kWh/an insécable ; phrase soir/nuit « la couvre » à ≥ 90 % sinon « en couvre N % » ; échéancier : dernier jalon = reste, puce CGV retirée quand les cartes sont imprimées ; phrase batterie une fois ; page finance « avec » sans texte de motif interne. Modules neufs : ci/options_cote.py, i18n_labels_ci.py, i18n_labels_ci_pages.py. Groupe CPDF ajouté à PLAN_AUDIT_MOTEUR.md (tâches encore [ ]).
RESTE: (1) fenêtre de tests : les 7 modules PDF lourds (ciq331/333/341/342/344/345, qx46) — leurs rouges pas encore relevés (≈ 11 rouges au run 1 ; les runs dépassent 45 min) ; (2) recapture des goldens C&I (commercial__*/industriel_etude__*) APRÈS #1114 et #1115 ; (3) rendus r3 + lecture de chaque page, critique Fable pré-merge, cocher CPDF1-10 + DONE LOG (décisions prises pour le fondateur : scénario prudent retiré, seuil 90 %, « estimée » gardé sur les prévisions) ; (4) merge origin/main, CODEMAP §4 + codemap_fingerprint --write (3 modules neufs), check_stages ; (5) reliquat round 2 : une-page C&I (bon pour accord/deux options), bande garanties depuis les fiches, pluriels AR/axe miroir, colonne SOURCE vide, libellé O&M répété, « MAD . » parasite ligne « Investissement (TTC, clé en main) » p3.
CONTRÔLES: 8 modules rapides (ciq302/305/307/320/330/343, amot36, amot41) = 85 tests, 2 rouges de libellé corrigés dans bd7e165ae — correctif non rejoué. Modules lourds NON vérifiés. flake8 propre.
ATTENTES: #1094 (economie_flux de l'option avec — mergée) ; #1114/#1115 pour les goldens ; jeton CI.
FICHIERS: quote_engine/ci/{blocs,couverture,synthese,mentions,onepage,categories,options_cote}.py, commercial/{cover,equip,trust}.py, industriel/{cover,finance,trust}.py, i18n_labels_ci.py, i18n_labels_ci_pages.py, tests ciq302/305/307/320/330/331/333/341/342/343/344/345, amot36, amot41, PLAN_AUDIT_MOTEUR.md.
PIÈGES: recette §4 du guide = moteur LEGACY (rendre via builder.registre_renderers, notes/CPDF-recette-rendu.md) ; tests du propriétaire devis probablement touchés : test_ciq315:122, test_ciq210_onepage_ci, test_figures_parite (parité via chiffres_cles, à vérifier) ; les modules lourds C&I dépassent 45 min en local.
