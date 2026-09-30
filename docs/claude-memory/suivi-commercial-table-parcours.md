# Suivi commercial : la table du parcours est LA source (30/09/2026)

**Décision fondateur (Reda, 30/09/2026)** : « look at it once and for all… make sure it makes sense… the
right set of answers after each step… every answer either leads to a different outcome or is just stored…
a PDF in my documentation module… test all the steps or make a testing script we can reuse. »

## Ce qui est établi (ne pas re-dériver)

- **Une seule table** décrit le suivi : `frontend/src/features/crm/relances/parcours_suivi.json`
  (types d'étape → question → réponses → ce que le serveur reçoit → suite machine → effet en prose).
  Elle est lue par (1) l'écran (`parcours.js`, ligne d'étape `RelanceEtapeRow.jsx`), (2) la garde de
  parcours serveur `apps/crm/tests_parcours_suivi.py` (rejoue chaque réponse par l'API réelle — tourne dans
  la CI à chaque merge ; en local : `powershell -File scripts/test-backend.ps1 -Modules "apps.crm.tests_parcours_suivi"`),
  (3) le guide PDF `docs/meryem/Suivi_commercial_etapes_et_reponses.pdf` généré par
  `scripts/generer_guide_suivi.py` et publié dans la GED (Documentation → Guides) par
  `publier_documents_meryem` à chaque déploiement. **Toute nouvelle réponse ou étape passe par la table**,
  jamais par une liste écrite à part dans un écran ou un test.
- **Verrou CAD44 précisé** (décision 21/09 « on ne coche pas un geste non fait » conservée, périmètre
  restreint) : les TÂCHES (préparer le devis, planifier la visite, décider la suite, devis modifié,
  question de prix) se traitent dès maintenant sans verrou ni « Sauter » ; l'issue d'un appel passé en
  avance se saisit toujours (enregistrée « traitée en avance ») ; un message ouvert depuis l'ERP ouvre
  « Fait ». Seul le « Fait » nu d'une touche du protocole à venir reste caché.
- **La planification s'ouvre AVANT tout enregistrement** (« Visite acceptée ») : date saisie → une seule
  requête qui clôt la touche ; « Date pas encore fixée » → la réponse seule et l'étape « Planifier la
  visite » est posée ; Annuler → rien n'est envoyé.
- Une touche traitée s'annule pendant 24 h (`ANNULATION_TOUCHE_HEURES`) ; « Perdu » est toujours un choix
  humain avec motif, jamais un effet de bord.

Pourquoi ici : trois surfaces (écran, test, guide) qui divergeaient ont bloqué Meryem après le script
d'appel ; la table unique est le contrat qui les tient ensemble.
