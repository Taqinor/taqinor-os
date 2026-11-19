# r2 — vague 3 : restes et demandes croisées, tenus au fil des plis

Plis faits (worktree `taches-r2-ci`) : CI api-fuzz ×4 (`d0bc4a9ff`), L2 temps 1 (`70e5d50cb`), L3 (`59888ee34`).

## Interfaces exposées
- (L3) événement `taqinor:taches:envoi` (`CustomEvent` sur `window`, constante `EVENEMENT_ENVOI` exportée par
  `features/taches/saisie/FeuilleSaisie.jsx`) : `{ etat: 'part', envoi, lignes: [{ client_id, titre, jour }] }` au
  toucher, avant tout appel réseau ; puis toujours l'un de `{ etat: 'creees', envoi, creees: [ITEM…] }`,
  `{ etat: 'echec', envoi }`, `{ etat: 'en_file', envoi }`. → L2, R3-030.
- (L2) `tachesApi` : avec `erreurSousLeChamp`, un 409 `state_conflict` ou un 404 qui nomme un champ revient à l'appelant
  sous la forme d'un 400 de champ (`response.status` = 400, vrai statut dans `response.statutServeur`), sans toast ni
  annonce. `lireAujourdhui(params, { suppressErrorToast })`.

## Demandes pour d'autres lanes
- (L3 → L7 `textes.md`) §2.3 alertes `deux_*` accordées (« Deux jours lus »…), « Plusieurs projets commencent ainsi :
  le premier est choisi. » ; aperçu de liste : bouton « Changer » (nom lu « Changer le projet : {nom} »), en-tête « Sans
  projet » ; toast « {N} tâches ajoutées ».
- (L3 → L1 `regles.md` §1.3) « jour décalage » : « N en chiffres, ou en lettres de un à trente » ; `projet` : « le nom
  d'un projet existant écrit avec ses espaces est lu en entier (le plus long) ».
- (L3 → L4 / L5 CSS) saisie en place au bureau : le titre « Aperçu de ta liste » n'apparaît pas (seul « 4 tâches ·
  2 projets ») ; iPhone : l'en-tête d'un groupe passe sur deux lignes avec « … · Changer » ; hauteur et défilement de
  l'aperçu en place (R3-094, L5).
- (L2 → L7 `textes.md`) « L'agenda n'a pas pu être lu » + « Réessayer » ; « Impossible de déplacer cette tâche ici. » ;
  « Une activité ERP s'ouvre dans l'ERP » · « Ouvrir ».
- (L2 → L6) `Projet.test.jsx` l.383, 398, 602 mockent le 409 NOMMÉ `nom_pris` alors que le serveur sert un 409
  `state_conflict` `{nom:[…]}` : à réaligner.
- (L2) R3-021 : le contrat de L1 dit `echeance === aujourd'hui`, pas `<=` comme la consolidation : trancher au pli de L1.
- (L2) démo `.demo-balayage` non réduite (taille de carte : R3-085, L5) ; la première tâche reste à y = 325-414 tant
  que la carte « 57 % » existe (part avec R3-005 de L1 et R3-085 de L5) : à re-mesurer après leurs plis.

## À rejouer sur l'écran après les plis (moitiés serveur)
- L3 : « Visite #cha » + Entrée lit tout « #Chantier Benali 9 kWc » ; « Relancer dans quinze jours » ; coller
  `liste30.txt` → « Projet : Recrutement technicien », « Projet : Administratif ».
- L2 : nom de projet pris → 409 `state_conflict`, toujours sous le champ ; `e2e/taches-journee.spec.js` jamais jouée.

## Après les plis de L1 (`ae490d3e3`) et L4 (`5ff286cb9`) — tête d'intégration `5f3a687d5`
- Contrat de L1 : `tour2/contrat-L1.md` ; nouvel échantillon `contract_samples/faites_semaine.json` ; plafond de
  requêtes de `priorites/` 22 → 23 (`test_plafonds.py`, `docs/query-budgets.yml`) : calculé, pas mesuré → la CI tranche.
- Écarts de L1 à la consolidation : l'avertissement `echeance_aujourdhui` reste `{code, message}` (pas de clé
  `echeance`) ; `total` / `activites_closes` sont dans l'enveloppe de `taches/?periode=faites_semaine`.
- Conséquence voulue de R3-001 : une ★ reportée au bilan du soir n'est plus comptée par la nuit ni dans l'essentiel de
  la Revue (« ce qui est montré est compté »).
- (L4 → L2, transmis) `Aujourdhui.test.jsx` l.989 rouge (« Calendrier… ») ; titres « Quand ? » (`Aujourdhui.jsx` l.940,
  `ATrier.jsx` l.323) ; mot du bilan perdu à la fermeture (`FeuilleBilan.jsx`) ; étoile qui change entre la liste et la
  fiche (deux valeurs d'`essentielle`).
- (L4 → L7) `textes.md` §2.4 l.195 : « Calendrier… », « Quand ? ».
- (L4 → L6, transmis) `GrilleAgenda` : appeler `retenirApercu(item)`.
- (L4) Échap avalé quelques millisecondes juste après un choix dans un menu ⋯ (Radix ; pareil sur main) ; l'appui long
  cache souvent la ligne surlignée sous la feuille ; `field-sizing: content` (champ de saisie qui grandit) à vérifier sur
  Safari réel.
- À rejouer sur l'écran (liste de L1, 10 gestes) : essentiel 1/2 partout ; ★ échue reportée ; une carte par jour ;
  semaine = 5 partout ; « Garder ce rythme » sur le pas réel ; Copilote sur journée trop pleine ; Alt+↓ près d'une ★ due ;
  derniers gestes ; pause puis recharger la Revue ; projets neufs sans « 0 a avancé ».
