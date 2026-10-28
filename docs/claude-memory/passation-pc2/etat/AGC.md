ETAT: MERGED — #1129 mergée par la file le 28/10 05:20 UTC (Groupe AGC1-AGC18)
BRANCHE: claude/pc2-agc-3cfefe @ 3e9390af1  PR: #1129 MERGED
FAIT:
- Validation R3, constats 2-5 corrigés (constat 1 = golden, Docker) :
  - 2a0d21c15 AGC11 : rien imprimé sur des mois du calendrier non confirmés (MOTIF_MOIS_CALENDRIER) ; « L'économie sera chiffrée après la visite du point d'eau » retirée FR/EN/AR.
  - 831ed228a AGC7 : formule du m³ (/proposition) seulement si economies.cas === 'nouveau_forage' ; garde source dans AGW304.
  - a321d9921 AGC9 : domain/pompage.derivees_de_l_etude persiste entrees_pompage.mode_pompe = mode EFFECTIF (pompe.mode, vide ⇒ neuve) ; CLES_ENTREES_POMPAGE + contrat etude_pompage_preview.json alignés ; règle plaque réservée aux études persistées avant.
- AGC14 scindée par propriétaire (check_ownership règle d) :
  - f5a8773db AGC14 contrat SEUL : proposal_data.json (backend + copie web identiques) › notes.agricole_agc14 + exemple_agricole.synthese_agricole.depense_declaree ; tâche déplacée dans PLAN_AUDIT_TRANSVERSE.
  - b3a4f861c AGC15 (moteur) : synthese_agricole sert depense_declaree ; pages._depense_declaree lit la même clé.
  - 107a41776 AGC16 (devis) : la case « Synthèse d'économies » du lien retire aussi depense_declaree (public_views +0 ligne).
  - def8594a5 AGC17 (web) : carte « Votre argent » + phrase neutre FR/EN/AR (data-agri-depense-declaree), montant au centime.
  - c1dab796d DONE LOG (MOTEUR, TRANSVERSE, DEVIS, WEB_PLAN) + 4 lignes dans decisions-prises.txt.
- Contrôles hôte VERTS : flake8 + py_compile ; check_stages ; codemap --check ; check_ownership ; check_forme_code --base origin/main ; check_api_shapes ; tsc -p tsconfig.check.json ; astro build.
- Tests hôte (Django 5.2 sur l'hôte, SimpleTestCase seulement) : 117 tests des 10 modules agricoles + test_agr304/310 AGC9/11/15 verts ; seules erreurs = environnement (weasyprint absent, base « db »).
- vitest (un fichier à la fois) : AGW304 35/35, AGW303 18/18, propositionPayload 79/79 (note agricole_agc14 justifiée), proposition 34/34, WJ32 26/26.
- Recettes prêtes (non commitées, exclues via .git/info/exclude) : backend/django_core/_agc_tests.py (saute toute TestCase : jamais la base de dev), backend/django_core/_agc_rendu.py (rollback, recette CPDF registre_renderers, full fr/en/ar + une-page fr/ar, texte par page en .pdf.txt).
- 28/10 03:20 : merges origin/main ff0963c6b + a58553623 (conflits = DONE LOG / groupes ajoutés des deux côtés, gardés tous ; goldens = version de main, à recapturer) ; AGC9 intact après AGV ; contrôles hôte re-verts (flake8, check_stages, codemap, ownership, forme_code, api_shapes, contrat identique, vitest AGW304 35 + payload 79, astro build).
- 28/10 fenêtre Docker : _agc_tests.py 118 OK ; harnais -RestoreDb 192 OK (goldens + AMOT63, AGR308, proposal_data_shape, quote_engine_formats, AGR306, AGR121) après suppression des clones test_erp_db_1..4 périmés (sans crm 0144) ; golden : seul legacy/onepage_agricole.json bouge (e8391ee58), agricole__* inchangés ; rendu R3 20 PDF lus (ligne neutre FR/EN/AR sans « après la visite ») ; devis auto depuis les leads de la base de dev = refus nommés (catalogue : structure_sol, STC, forage) → AGC9 prouvé par tests base, pas par rendu.
RESTE (fait sauf Fable/PR) :
  1. _agc_tests.py dans le conteneur (PDF réels weasyprint des 10 modules).
  2. Harnais base : powershell -File scripts/test-backend.ps1 -RestoreDb -Modules "apps.ventes.tests.test_amot63_entrees_resolues apps.ventes.tests.test_agr308_synthese_agricole_servie apps.ventes.tests.test_proposal_data_shape apps.ventes.tests.test_quote_engine_formats apps.ventes.tests.test_agr306_mentions_agricoles"
  3. Rendu réel R3 : _agc_rendu.py (ROUND=r3, AGM_TEST_PRIX=1, AGC_REGLAGES=1), lire chaque page (ligne neutre sans « après la visite », pompe neuve ≠ « existante »).
  4. Golden legacy/onepage_agricole.json (constat 1) + build_quote_data/agricole__* : #1114 mergée et fusionnée → UPDATE_GOLDEN=1, ne garder que les fichiers agricoles.
  5. Fable R4 (œil client) + critique Fable pré-merge, puis UNE PR au JETON CI.
ATTEND: rien (jeton CI à passer). Restant hors périmètre : rejeu en direct AMOT65 (orchestrateur avec pile) ; étiquette « 37 m³/h · 4 » coupée (schema.py) ; note « hors bande 1,2-1,5× » au client ; centimes d'une dépense déclarée.
DECISIONS: (prises pour le fondateur, à revoir)
- AGC : ligne neutre = la somme déclarée seule (plus de « chiffrée après la visite »).
- AGC : mode de pompe persisté = mode effectif étudié (vide ⇒ neuve).
- AGC : AGC14 scindée en 4 tâches, livrée dans une PR, contrat commité seul en tête.
- AGC : la dépense déclarée suit la case « Synthèse d'économies » du lien.
À SIGNALER (critique Fable) : la ligne neutre AGC11/AGC17 s'affiche aussi sur un devis DÉJÀ ENVOYÉ re-rendu (texte nouveau, pas un chiffre corrigé) — non gardée par regles_au_moins ; à trancher.

- 28/10 Fable R4 (1 appel) : bloquant B1 corrigé 1bf87caea (plus de « pompe existante » déduite de la plaque seule) ; AGC18 88b354e32 (« CV » traduit une-page EN/AR) ; décision « TEXTE non gardé par regles_au_moins » consignée ; hors périmètre : étiquette « 37 m³/h · 4 » coupée (schema.py), note « hors bande 1,2-1,5× » au client, centimes d'une dépense déclarée.
- 28/10 04:50 : corrections CI — D-AGC-1/2/3/6/7 ajoutées à decisions.yml (+ tags =a) ; AMOT65 décochée (rejeu en direct dû, CLAUDE.md 3-bis) ; bande /pompage-solaire extraite en components/blocs/BandeCapacitePompage.astro (duplicat ACAL345) ; ci_guards stage-names vert en local ; astro build OK.
- 28/10 ~05:00 : CIW406 (web-build-test) — main latent rouge depuis CSV13 (#1123, backend seul : web-build-test sauté) : clés d'heures ajoutées aux clés fermées ; test aligné (chaque liste web = sa part du contrat, ordre du contrat), aucun code questionnaire touché. Pas de copie web de questionnaire_lead.json (le test lit le backend). estimatorRuntimePro10Pro11 / userJourneyPro11 rouges en local = environnement (junction node_modules « Denied ID »).
DONE LOG À POSER (PR docs de clôture) — correction hors groupe CIW406, mergée dans #1129 (3e9390af1) :
- Fichier touché : apps/web/tests/questionnaire.test.ts (test « questions de catégorie = clés fermées du contrat ») ; aucun code questionnaire, aucun contrat modifié (il n'existe pas de copie web de questionnaire_lead.json).
- Le test compare désormais REPONSES_CATEGORIE_QUESTIONS[cat] aux clés NON-heures de lead_pro.json › reponses_categorie_par_categorie.cles, REPONSES_CATEGORIE_HEURES[cat] aux clés d'heures (ordre du contrat), et leur union à toutes les clés.
- Pourquoi : CSV13 (#1123, backend seul, web-build-test sauté) a ajouté heures/heures_cuisson/heures_garde/fermeture_du/au aux clés fermées ; le site les tient dans REPONSES_CATEGORIE_HEURES (CQSTW6) — les recopier dans les questions les rendrait deux fois.
ETAT FINAL : lane AGC terminée (AMOT65 + rejeu en direct → CE2E).
