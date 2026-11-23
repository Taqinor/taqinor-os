# Coutures de la vague D, second tour — ce que le rejeu en direct T3-VAGUED a vu

Source : `docs/audits/l5-calepinage/registre/evenements/T3-T3-VAGUED-cv.jsonl` (lignes ADEV125, ADEV127, ADEV123 :
champs `preuve` et `reste`) — LIS-les avant d'écrire. Règles : `docs/audits/l5-calepinage/T2/brief-lanes.md` (en
entier) et « Communs à toutes les lanes » de `docs/audits/l5-calepinage/controles/lanes-vague-D.md`. Branche LOCALE
d'intégration : `git checkout -q -B <ta branche> claude/calpinage-module-l5-aadbde` (tête « Calepinage L5 : critique
finale des vagues C et D » ou plus récente). Un commit par point, test rouge d'abord dans le module de test EXISTANT ;
aucun `git push` ; aucun `docker compose` ; tu n'édites ni `docs/plans/*`, ni `docs/CODEMAP.md`, ni
`docs/openapi-schema.yml`. Demande du fondateur, mot pour mot : « my ERP should be able to solve and have default for
everything should only need the bill and one consumption profil picked ».

## Lane « couture-suppositions » (`apps/crm`, `apps/ventes`, écrans du devis automatique) — branche `lane-l5d-couturesuppositions`

1. **ADEV127, le régime d'équipes suffit (D-ACAL-94, réponse du fondateur : `regime_suffit`)** — vu en direct : un
   lead industriel en 2 × 8 sans heure de début est refusé (« Manque : Jours et heures d'ouverture (ou catégorie
   d'activité) »), alors que 3 × 8 passe. Cause à lire : `backend/django_core/apps/ventes/moteur_ci/charge.py::
   profil_charge_prerequis` (l'heure de début d'équipe est exigée en 1 × 8 et 2 × 8) et la garde
   `backend/django_core/apps/crm/devis_auto.py::_groupes_rythme`. Attendu : régime déclaré sans heure de début ⇒ une
   heure de début SUPPOSÉE (1 × 8 : 8 h ; 2 × 8 : 6 h — une constante nommée par régime, à côté des autres
   suppositions de `backend/django_core/apps/ventes/domain/suppositions_ci.py`), dite à la commerciale avec son champ
   (`heure_debut`), statut « estimation », source « décision fondateur du 23/11/2026 (D-ACAL-94) » ; la fiche dit le
   lead prêt ; le devis automatique aboutit. Une heure de début DÉCLARÉE prime toujours. Les jours supposés
   (lundi-samedi) restent ceux d'ADEV127.
2. **D-ACAL-92 pour l'industriel (réponse du fondateur : `supposer_bt`, question posée pour « un lead commercial ou
   industriel »)** — vu en direct : un lead industriel avec une facture en dirhams et SANS tension déclarée est refusé
   (« … ou facture en MAD si la basse tension est déclarée »). Cause à lire : `apps/crm/devis_auto.py::
   _facture_mad_compte` et `_tension_declaree`, et côté moteur `apps/ventes/domain/etude_ci.py::refus_devis_auto_ci`.
   Attendu : tension NON déclarée (vide, « ne sait pas », défaut du site jamais touché) ⇒ basse tension supposée,
   dite avec le champ `tension_raccordement`, devis marqué estimation ; le libellé du groupe industriel
   (`_LIBELLES_PRO`) et l'échantillon de contrat `apps/crm/contract_samples/devis_auto_pret.json` suivent dans le
   même commit, ainsi que tout lecteur front du libellé. Une tension DÉCLARÉE « mt » garde EXACTEMENT sa règle
   d'aujourd'hui (aucune facture en dirhams convertie au tarif basse tension) ; `visite_avant_devis` continue de dire
   « tension de raccordement inconnue ».
   `apps/ventes/domain/etude_ci.py` fait 2 013 lignes : il ne grossit PAS (mets le code neuf dans
   `suppositions_ci.py` ou un module voisin ; `python scripts/check_forme_code.py --base origin/main` doit rester vert).
3. **ADEV123 à l'écran** — vu en direct : la réponse de `POST /ventes/devis/auto/` d'un lead résidentiel porte quatre
   alertes avec leur champ (`suppose_presence`, `suppose_ete_egal_hiver`, `suppose_kwh_depuis_facture`,
   `suppose_30_plein_sud`) mais l'écran n'en montre AUCUNE (le panneau n'a que « Devis créé : … »), alors que le devis
   C&I en montre 12. Cause donnée par le vérificateur : `frontend/src/features/ventes/autoQuote.js`, branche
   résidentielle — `onResultat` est appelé mais pas `onAlertes` ; lecteurs : `frontend/src/pages/crm/leads/
   LeadDevisPanel.jsx`, `frontend/src/pages/ventes/generator/hooks/useLeadClientEcran.js`. Attendu : les suppositions
   résidentielles s'affichent comme celles du C&I (même composant, « À compléter sur la fiche : <champ> »).
4. **Les suppositions survivent à la réouverture (ADEV123 et ADEV125, clause « Persistance »)** — vu en direct :
   rouvrir le devis ne remontre aucune supposition ; `etude_params.etude_ci.alertes` ne garde pas les codes
   `supposition_*` (seules restent des hypothèses sans champ de la fiche) et le devis résidentiel n'a pas de
   `journal_auto` rangé. Attendu : les suppositions dites à la création (code, phrase, champ de la fiche) sont RANGÉES
   avec le devis et remontrées à la réouverture de son écran, pour le résidentiel comme pour le C&I. Contraintes :
   (a) rien de neuf dans le PDF client (`/proposal`) — ces phrases sont pour la commerciale ; (b) une clé rangée
   neuve ne doit PAS entrer dans l'empreinte qui déclenche un recalcul (`cles_hors_empreinte` pour le C&I ; pour le
   résidentiel, lis comment `etude_params` est comparé) ; (c) un devis ENVOYÉ n'est jamais réécrit ; (d) contrat
   d'abord : si une clé servie neuve apparaît, son échantillon `contract_samples/*.json` est écrit dans le même
   commit que le serveur, et le front qui la lit cite le NOM du fichier dans un test (`check_api_shapes.py`).
5. **Le refus dit ce qui manque vraiment** — si, après 1 et 2, il reste un cas où le refus nomme « Jours et heures
   d'ouverture » alors que seule l'heure manque (ou l'inverse), corrige le libellé ; sinon écris « sans objet ».

Avant ton rapport : `python -m flake8 --max-line-length=120` sur tes fichiers ; par `tester.sh` (nom court
`couturesup`) : `apps.crm.tests_devis_auto apps.crm.tests_devis_auto_contrat apps.ventes.tests.test_ciq120_devis_auto_ci
apps.ventes.tests.test_ciq666_contrat_lead_devis_auto apps.ventes.tests.test_qjr_bascule_auto
apps.ventes.tests.test_devis_auto apps.ventes.tests.test_auto_pipeline apps.ventes.tests.test_ciq118_etude_ci_preview
apps.ventes.tests.test_ciq119_rafraichir_ci` + tout module de test que tu touches (le golden HTTP du CRM
`apps.crm.tests_scission_golden` a besoin de `freezegun`, absent de l'image : dis-le si tu changes une clé qu'il
capture, l'orchestrateur le rejouera) ; `npx eslint` sur tes fichiers front, `npx vitest run` sur les tests touchés
et sur `src/features/ventes/autoQuote*.test.jsx`, `node --test "src/features/ventes/*.test.mjs"
"src/features/crm/**/*.test.mjs"` depuis `frontend/` ; `python scripts/check_api_shapes.py`,
`python scripts/check_services_appeles.py`, `python scripts/check_forme_code.py --base origin/main`,
`python scripts/check_duplicats_litteraux.py`. Dis dans ton rapport, pour chaque point : commit, test rouge puis
vert (commande et sortie), et ce que tu n'as PAS vérifié.
