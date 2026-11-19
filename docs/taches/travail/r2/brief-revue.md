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

---

## Tours 2 et suivants — ce qui change pour toi

Le tour 1 a trouvé 152 constats, consolidés en 102 corrections (`tour1/consolidation.md`, identifiants `R2-NNN`),
corrigées par onze lanes puis une lane de couture ; les restes connus sont dans `vague2.md`. La pile sert maintenant
le code CORRIGÉ (branche `dev-taches-r2`), front et serveur. Tu es un relecteur NEUF : tu n'as pas vu le tour 1.

Ton travail a deux moitiés, dans cet ordre :
1. **Contre-vérifier** (adversaire, pas complaisant) : pour chaque correction `R2-NNN` de ton périmètre (liste dans ton
   prompt), rejoue sur l'écran réel le geste du constat d'origine (lis-le dans `consolidation.md` ; le rapport du
   relecteur d'origine est dans `tour1/`) et classe : **réglé** (capture), **réglé à moitié** (ce qui manque),
   **pas réglé**, **régression** (la correction a cassé autre chose : quoi). Cherche surtout les jumeaux oubliés : le
   même défaut sur l'autre écran, l'autre thème, l'autre taille, l'autre chemin (clavier / doigt / menu).
2. **Regard neuf** : refais le parcours de ton rôle comme si tu découvrais l'outil et relève ce qui reste sous le
   niveau des meilleurs (mêmes règles de preuve et de gravité que plus haut). Ne répète pas un constat écarté au
   tour 1 pour une raison écrite (`consolidation.md` § 2 : artefacts de la pile, hors module) sauf si tu as une
   raison nouvelle.

Rapport `docs/taches/travail/r2/<tour>/<ton nom>.md` : verdict en trois lignes ; tableau de contre-vérification (une
ligne par `R2-NNN` : état, capture, remarque) ; tableau des constats NEUFS (même forme qu'au tour 1) ; ce qui est bien ;
non essayé. Message final : verdict + nombre de réglés / à moitié / pas réglés / régressions + constats A neufs,
15 lignes au plus.

---

## Tour 3 — dernier tour avant de rendre le module à Reda

Le tour 2 (cinq relecteurs neufs) a donné 84 corrections `R3-NNN` (`tour2/consolidation.md` : § 0 les six sujets
majeurs M1-M6, § 1 le texte de chaque correction, § 3 les choix C-13 à C-24), corrigées par sept lanes ; ce qui a été
laissé est dans `vague3-restes.md`. La pile sert le code final de la branche `dev-taches-r2`, front et serveur. Tu es
un relecteur NEUF. Même méthode qu'au tour 2 (contre-vérifier, puis regard neuf), avec trois différences :
1. La contre-vérification porte sur les `R3-NNN` de ton périmètre (et, par sondage, sur les `R2-NNN` graves du tour 1 :
   une correction du tour 1 a pu être cassée par la vague 3 — cherche les régressions).
2. Chaque constat neuf porte, en plus de sa gravité, un avis net : **avant le merge** (Reda le verrait dans sa première
   heure d'usage, ou c'est une perte de données, un chiffre faux, un geste courant cassé) ou **peut attendre** (finition).
3. Ton rapport se termine par un jugement en dix lignes au plus : ce module, tel qu'il est sur l'écran, peut-il être
   mis entre les mains de Reda aujourd'hui en disant « voici le meilleur que nous sachions faire » ? Si non, les CINQ
   choses qui manquent, dans l'ordre. Sans politesse : un « oui » complaisant coûte plus cher qu'un « non » argumenté.
