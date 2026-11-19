# r2 — ajouts de l'orchestrateur à la vague 3 (hors rapports des relecteurs)

Vus en CI (PR 1481) ou sur la pile, à donner à la lane qui possède le fichier :

- **Saisie — une lettre perdue après le choix d'un projet dans la liste `#`** (`features/taches/saisie/FeuilleSaisie.jsx`,
  `ui/ChampSaisie.jsx`). Test `FeuilleSaisie.test.jsx` « R2-003 — sans accents ni casse, flèches puis Entrée, ou au
  doigt ; Échap ferme la liste, pas la feuille » : vert sur le poste, ROUGE en CI sous charge (shard vitest 2, tête
  `2d65165d6`) : attendu « Photos #Site_web et #Chantier_Bénali_9_kWc », reçu « Photos #Site_web t #Chantier… » — le
  « e » tapé juste après l'insertion du projet est avalé. Même famille que R2-001 : l'insertion du jeton réécrit le
  champ à partir d'une valeur périmée. Correction à la racine (insertion calculée sur la valeur COURANTE du champ, au
  moment de l'écriture ; rien d'asynchrone entre le choix et l'écriture), test qui tape la suite SANS attendre
  (plusieurs frappes enchaînées dans le même `act`), rejoué 20 fois de suite.
- **Cloche de l'en-tête** : nom lu « Notifications : 14 » (axe-core 4.14 de la CI refuse « Notifications (14) » avec
  la pastille « 14 ») — FAIT (`2d65165d6`). Le `node_modules` du poste porte axe 4.12.1 : une spec axe verte ici ne
  prouve rien ; vérifier contre 4.14.0 (`…\scratchpad\r2\orchestrateur\axe414\package\axe.min.js`, script
  `axe-cloche3.cjs` à côté).
- L'outil `capturer-reel.cjs`, étape `menu-ligne` : touche l'étoile cachée sous le bouton invisible et modifie le
  compte (signalé par T2-B1) : corriger le geste du script (appui long ou ⋯ visible).

## Après le pli de la lane CI (`1b24f3474`, tête d'intégration `74f52651b`)
Le contrôle api-fuzz n'avait JAMAIS lu les corps des routes Tâches (le compte de fuzz recevait 403 jusqu'à TCH168) :
≈ 46 constats latents, corrigés à la racine. Ce que ça change pour les autres lanes :
- Toutes les vues lisent du JSON seul (sauf `capture/`).
- Un REFUS D'ÉTAT répond maintenant **409** avec le même corps qu'avant (nom déjà pris : projet, étape, modèle,
  étiquette, vue ; 30 vues atteintes ; 3 essentielles déjà posées ; bilan fermé ; agenda externe injoignable, en
  doublon ou au plafond ; incohérence `du`/`au`). Un identifiant envoyé qui ne désigne rien répond **404**, même corps.
  Un 400 reste le refus de FORME (champ manquant, mal typé, hors liste).
- **À faire côté écran (lane L2, qui possède `api/tachesApi.js`)** : un nom déjà pris arrive en 409 → `tachesApi`
  l'affiche en TOAST au lieu de le dire sous le champ (l'option `erreurSousLeChamp` ne couvre que les 400). L'option
  doit couvrir les 409 de champ (corps portant un nom de champ) : message sous le champ, pas de toast ; même chose pour
  l'agenda externe (trois messages) et tout appelant qui affichait un 400 sous un champ. Tests front à réaligner sur
  les VRAIS codes (les mocks rendent encore 400) ; specs e2e qui attendent un message sous le champ à rejouer.
- Peuvent encore remonter en api-fuzz (400 gardés exprès) : `projet_id` inconnu dans une ligne de `POST taches/` ou
  `saisie-rapide/` (« Projet inexistant. »), `conges` avec `au` avant `du`.

## Table des réponses passées de 400 à 409 ou 404 (lane CI, tours 1 et 2 — pliée, tête `28faf43ed`)
Corps : 409 = `{champ…, detail, code: "state_conflict"}` ; 404 = `{champ…, detail}`. Un 400 reste un refus de FORME.
| Route | Refus | Code |
|---|---|---|
| POST `projets/`, PATCH `projets/{id}`, `dupliquer/`, `modeles/{id}/instancier/` | « Un projet « X » existe déjà. » | 409 |
| POST et PATCH `sections/` | « Une étape « X » existe déjà. » | 409 |
| `enregistrer-modele/`, PATCH `modeles/{id}` | « Un modèle « X » existe déjà. » | 409 |
| POST et PATCH `etiquettes/` | étiquette déjà existante | 409 |
| POST et PATCH `vues/` | vue déjà existante, « 30 au plus. » | 409 |
| `journee/planifier/`, `journee/essentiel/` | « 3 au plus. » avec des ★ déjà posées | 409 |
| GET `journee/cloture/`, POST `journee/cloturer/` | bilan d'hier fermé, jour trop ancien | 409 |
| GET `agenda/` | `au` avant `du`, « 42 jours au plus. » | 409 |
| POST `agendas-externes/` | injoignable (DNS), doublon, 3 au plus | 409 |
| POST `taches/{id}/reordonner/` | liste « jour » d'une tâche sans jour | 409 |
| POST `taches/lier-activite/` | titre vide et activité sans résumé | 409 |
| POST `sections/` | `projet_id` inconnu | 404 |
| POST `taches/lot/` (`deplacer`) | projet cible inconnu | 404 |
| POST et PATCH `vues/` | filtres `projets` / `etiquettes` inexistants, seuls | 404 |
| POST `taches/`, `saisie-rapide/`, PATCH `taches/{id}` | lien « Élément introuvable ou hors de ta portée. » | 404 |
| POST `projets/{id}/terminer/` | `projet_cible_id` inconnu | 404 |
| POST `saisie-rapide/` avec `lignes` par le canal assistant (Bearer) | refus de canal (à venir, commit suivant) | 403 |
Côté écran (lane L2, `tachesApi.js`) : un 409 `state_conflict` ou un 404 qui porte un NOM DE CHAMP et dont l'appelant a
demandé `erreurSousLeChamp` se dit sous le champ, sans toast. Vu en CI : `e2e/taches-projets.spec.js:164` « une adresse
d'agenda refusée l'est sous le champ » échoue tant que ce n'est pas fait.
