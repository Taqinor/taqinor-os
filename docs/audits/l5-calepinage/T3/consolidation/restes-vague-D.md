# Restes de la vague D — à écrire en tâches v3 chez le propriétaire des fichiers

Sources : critique finale `docs/audits/l5-calepinage/T3/critique-finale-vagues-C-D.md` (section « Après » et « Ce qui
n'a pas été lu »), rejeu en direct `docs/audits/l5-calepinage/T3/T3-VAGUED.md` +
`registre/evenements/T3-T3-VAGUED-cv.jsonl` + `registre/constats/T3-T3-VAGUED.jsonl`, rapports des deux lanes de
couture du second tour (`…/scratchpad/l5b/T2-lane-couturesuppositions.jsonl`, `T2-lane-coutureresultats.jsonl` :
lignes « impossible », « non reproduit », « demande croisée »). Une ligne = une tâche à écrire, sauf mention « déjà une
tâche » (alors : ne rien écrire, citer l'id).

## Plan du calepinage (`docs/plans/PLAN_AUDIT_CALEPINAGE.md`)

1. **Rejeu en direct dû — ombrage proche avec obstacles (ACAL1407)** : non joué par T3-VAGUED (temps). Tâche
   d'ACCEPTATION (orchestrateur, jamais une lane) : obstacle haut au centre d'un pan dont les panneaux sont ailleurs ⇒
   perte proche faible ; obstacle devant les panneaux ⇒ perte dite ; deux simulations, chiffres relevés.
2. **Rejeu en direct dû — rapport d'étude PDF à deux productions (ACAL1956, ACAL1755)** : le PDF n'a été ni généré ni
   lu ; cas « productions égales ⇒ un seul chiffre » non joué ; clic « Réviser le devis » non fait. Tâche d'ACCEPTATION.
3. **Rejeu en direct dû — NASA POWER quand le service répond (ACAL746)** : injoignable depuis la pile de revue ; à
   jouer sur un poste qui sort sur Internet. Tâche d'ACCEPTATION.
4. **Mode Expert après création (constat T3-T3-VAGUED-009, S3)** : à l'étape Panneaux, l'éditeur Expert affiche une
   page de champs sans habillage (champ « Agadir », champs vides « Date de la photo », « Rangs par châssis », boutons
   de carte superposés), bien moins finie que le Guidé. Vérifier d'abord si une tâche ouverte le couvre (chercher
   « Expert » dans le groupe du 2026-11-23) ; sinon l'écrire.
5. **Page d'aperçu `/preview/toiture-3d-pro-11` (critique finale, point 6)** : hors mode disposition le bouton Annuler
   appelle maintenant `ctx.annulerGeste` pour tous les modes, et `optimizer.ts::maxSensCarte` /
   `shadingUi.ts::matriceOmbrageDesSources` ne sont pas réservés à l'ERP : dire si c'est voulu sur la page d'aperçu
   publique, sinon réserver à `opts.chiffrage` ; test du moteur.
6. **Tenue de la pose en placement LIBRE (critique finale, « non lu »)** : après un changement de toit, de module ou
   d'obstacle en placement libre (`freeState`), la pose rejouée n'a été suivie par personne ; tâche de vérification
   avec test du moteur (et correctif si un défaut est lu).
7. **Chaque document différent enregistré soumet un job de simulation (critique finale, « optionnel »)** : le marqueur
   ne dédouble que la même empreinte ; sous une rafale d'enregistrements, N jobs partent (les retardataires répondent
   « déjà calculé »). Regrouper (un seul job en attente par calepinage). S4.

## Plan du devis (`docs/plans/PLAN_AUDIT_DEVIS.md`)

8. **Le devis résidentiel ne lit pas encore le froid du site (reste d'ADEV122)** : seules les chaînes du devis C&I
   sont bornées au minimum de l'année type du lieu ; le résidentiel garde −5 °C partout. Nouveaux calculs seulement,
   goldens recapturés par la procédure, hypothèse dite.
9. **La garde « catalogue C&I prêt » ne liste pas tous les postes sans prix (constat T3-T3-VAGUED-008, S3)** : la
   fiche dit le lead prêt une fois les forfaits et trois articles tarifés, puis le moteur refuse en 409 (« Prix à
   renseigner avant un devis automatique C&I : câble solaire 4 mm², câble AC 5 × 10 mm², structure toit plat lestée,
   protection DC par chaîne, parafoudre DC par chaîne »). Une seule liste, celle du moteur, lue par la garde.
10. **Deux tests de pages du devis C&I déjà rouges sur `main`** : `apps.ventes.tests.test_quote_engine_amot36_pages_ci`
    (2 échecs antérieurs à la campagne ; chercher « PROPRES À CETTE OPTION ») — va dans `docs/ERROR_PLAN.md` si le
    propriétaire des fichiers est le moteur de PDF ; vérifier d'abord qu'aucune ligne ERR ne le porte.

## Plan transverse / déploiement

11. **Trois tests du rapport d'étude rouges sur `main` hors étage PDF**
    (`apps.calepinage.tests.test_acal_rapport_etude_servi.SchemaJointAuRapportTest`, 3 erreurs « Aucun résultat de
    moteur enregistré ») : dire s'ils sont réservés à l'étage PDF de la CI (alors les y étiqueter) ou réellement
    cassés ; aujourd'hui ils échouent dans tout passage local de la suite du calepinage.
12. **`freezegun` absent de l'image de test locale** (`testkit.time`) : 6 modules ne se chargent pas dans le
    harnais local (`apps.crm.tests_scission_golden` et cinq modules du calepinage) ; l'ajouter aux dépendances de test
    de l'image, ou le dire dans `scripts/test-backend.ps1`.

## Déjà des tâches — ne rien écrire, seulement vérifier qu'elles sont ouvertes

- ACAL1957 (« cible vide » après « Générer le devis ») ; ACAL1984 (panneaux noirs) ; ACAL1907 (barre sombre) ;
  les 55 tâches du chantier « un seul moteur » (D-ACAL-97) ; les six écrans à refaire sur les maquettes v2.
