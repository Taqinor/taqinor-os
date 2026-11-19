# Brief commun des relecteurs — tours de revue du module « Tâches » sur l'écran RÉEL

## Pour qui on juge

Reda, fondateur de TAQINOR (installateur solaire au Maroc), non-codeur, vit sur son iPhone. Il a essayé beaucoup de
gestionnaires de tâches sans en aimer aucun et a demandé le sien dans son ERP : des tâches dans des projets à
priorités, qui remontent dans sa liste du jour ; ajouter une tâche en un geste ; planifier ; un Copilote qui l'aide à
prioriser et à tenir son rythme (« en faire plus » ou « garder le pas ») ; l'outil qui le suit partout. Son exigence,
mot pour mot : « the best in term of ease of use and prettiness », « la meilleure agenda possible, toutes les
fonctionnalités nécessaires et utiles et en même temps simple et facile à utiliser », « i expect the best ».
Le module est construit et sur `main`. Ton travail n'est PAS de relire du code : c'est d'UTILISER le produit réel
comme lui, de le regarder, et de dire sans complaisance ce qui n'est pas au niveau.

## Ce que tu as sous la main

- La pile locale décrite dans `docs/taches/travail/r2/pile-locale.md` (LIS-LE EN PREMIER : adresse du front, comptes
  de revue, comment réinitialiser TON compte, outil de capture). Tu as UN compte à toi (donné dans ton prompt) : ne
  touche jamais aux autres comptes ; tu peux tout faire avec le tien (créer, supprimer, « Tout effacer »,
  réinitialiser sa journée d'exemple autant de fois que tu veux).
- Playwright : `C:\dev\taqinor-os\frontend\node_modules\playwright` (Chromium). Tu écris tes propres scripts `node`
  (dans `C:\Users\kasri\AppData\Local\Temp\claude\75bbe857427ccce5\b797bc27-f912-4ba8-a54b-d982221d7224\scratchpad\r2\<ton nom>\`)
  qui se connectent, font de VRAIS gestes (clics, frappe, glisser, clavier), et prennent des captures que tu REGARDES
  ensuite avec l'outil Read (une image se lit comme un fichier). iPhone = 390 × 844, tactile, échelle 2 ; bureau =
  1440 × 900. Clair et sombre.
- La galerie de départ : `…\scratchpad\r2\captures\tour0\` (+ `index.md`) : tous les écrans déjà capturés en 4 vues.
- L'intention : les maquettes `docs/taches/maquettes/*.html` (+ `SCENARIO.md`, captures dans
  `docs/taches/maquettes/captures/`), la référence `docs/taches/reference/{textes,regles,api}.md` — à lire dans le
  worktree `C:\dev\taqinor-os\.claude\worktrees\taches-r2` (code de `main`). L'état des lieux de ce qui a été livré,
  laissé ouvert ou décidé seul : `docs/taches/travail/r2/etat-des-lieux.md` (LIS-LE : ne redécouvre pas ce qui est
  déjà connu, mais tu peux juger qu'un écart « laissé » est en réalité inacceptable).

## Règles

- Tu n'édites AUCUN fichier du produit. Tes seules écritures : tes scripts et captures (scratchpad), et TON rapport.
- N'arrête ni ne relance la pile ; ne lance aucune commande `docker compose` ; ne touche pas aux conteneurs
  `erp-agentique-*` (une autre session s'en sert). Si la pile ne répond plus, dis-le et arrête-toi.
- Chaque constat doit être PROUVÉ : les gestes exacts pour le reproduire + la capture (chemin) où on le voit + ce
  que tu attendais à la place. Un constat que tu n'as pas vu de tes yeux sur l'écran réel n'entre pas dans le rapport
  (au mieux dans une section « à vérifier »).
- Calibrage : un constat = quelque chose que Reda remarquerait ou qui le ferait hésiter, chercher, se tromper,
  perdre du temps, ou trouver l'outil moins beau ou moins sérieux que les meilleurs (Things 3, Todoist, TickTick,
  Apple Rappels et Calendrier, Sunsama, Linear). Pas de préférence personnelle sans raison ; pas de durcissement
  hypothétique. Gravité : **A** = casse ou bloque un geste courant, ou défaut qui saute aux yeux ; **B** = gêne ou
  laideur visible au quotidien ; **C** = finition.
- Dis aussi ce qui est BIEN (à ne pas casser) et ce que tu n'as PAS pu essayer.
- Écris au fil de l'eau dans ton rapport (crée-le tôt, ajoute chaque constat dès qu'il est prouvé) : si la session
  est coupée, seul ce qui est dans le fichier est gardé.

## Forme du rapport (français simple)

`docs/taches/travail/r2/<tour>/<ton nom>.md` :
1. Verdict en trois lignes (le niveau réel, sans politesse).
2. Tableau des constats : n°, gravité, écran, ce qui se passe (gestes), capture, ce qu'il faudrait, piste de
   correction en une ligne (fichier probable si tu l'as trouvé en lisant `frontend/src/features/taches` ou
   `frontend/src/pages/taches`, sans obligation).
3. Ce qui est bien et doit rester.
4. Non essayé, et pourquoi.
Ton message final : le verdict + les constats A, en 15 lignes au plus.
