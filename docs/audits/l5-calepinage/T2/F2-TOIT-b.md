# F2-TOIT-b — contre-vérification des 20 corrections (étape Toit, seconde moitié) — tour 2

Compte `rev_b3`, bureau 1440 × 900, thème clair (sombre pour ACAL1294). Pile `l5cal` (code `origin/main@bfb859c90`). Scripts et captures : `scratchpad/T2/F2-TOIT-b/`.

## 1. Verdict en trois lignes
- 20 corrections jouées sur l'écran réel : 12 tiennent, 5 sont partielles, 2 ne sont pas faites sur l'écran, 1 a cassé quelque chose.
- Le défaut grave : cocher « Pan existant » (ACAL510) puis enregistrer rend le calepinage impossible à rouvrir (toit non dessiné, case impossible à décocher).
- Deux corrections (ACAL1291 liste des obstacles, ACAL533 tableau « Objets du site ») partagent la même panne : le tableau n'est redessiné que si l'on change de pan.

## 2. Comptes
ok 12 · partiel 5 · non-fait 2 · faux 0 · régression 1 · déjà-présent 0 · non essayé 0 (deux preuves jouées avec une réponse simulée, voir §5).
Cases de matrice de classe : non jouées (la fiche de lancement ne cite aucune classe K pour cet écran ; mission = contre-vérification seule).

| id | verdict | en une ligne |
|---|---|---|
| ACAL510 | **regression** | case, année, refus et enregistrement OK ; mais un calepinage enregistré avec un pan existant ne se rouvre plus (S2) |
| ACAL508 | non-fait | aucune ligne d'origine de l'image : l'atelier ERP ne passe jamais `imagery` |
| ACAL1291 | non-fait | la section « Obstacles » n'affiche aucune ligne, même après enregistrement et réouverture |
| ACAL509 | partiel | saisie, refus, enregistrement OK ; à la réouverture les champs restent vides ; champs sans bordure |
| ACAL511 | partiel | plan 2D hachuré + légende OK ; étiquette « Existant 2019 » absente de la liste et du tableau |
| ACAL515 | partiel | contrôles et refus OK ; le pivotement lui-même n'a pas pu être joué (pas de site sans panneau) |
| ACAL520 | partiel | 3 refus OK ; le nom dans le message (« Zone 2 ») n'est pas celui de la liste (« Zone 1 ») |
| ACAL533 | partiel | tableau correct une fois affiché ; absent tant qu'on ne change pas de pan |
| ACAL507, 513, 529, 531, 535, 536, 537, 763, 764, 1185, 1289, 1294 | ok | voir le fichier de verdicts |

## 3. Constats neufs (registre `T2-F2-TOIT-b.jsonl`)
- 001 S3 K7 — champs « Date de la photo » / « Source » sans bordure ni fond (16 px de haut).
- 002 S3 K2 — nom des pans incohérent après « 2 pans » : liste « Zone 1/2 », message/aria/document « Zone 2/3 ».
- 003 S3 K7 — panneau Expert : valeurs des totaux et boutons de ligne de pan se chevauchent.
- 004 **S2 K1** — réouverture impossible d'un calepinage avec « Pan existant » (voir ACAL510).
- 005 S3 K6 — la bascule Guidé → Expert ne révèle « Exporter la 3D (glTF) » et « Vidéo 10 s » qu'après rechargement (deux `useModeExpert()` indépendants).
- 006 S3 K7 — onglet Plan importé : champs gris pleins, « Choose File » en anglais.
- 007 S4 K7 — « 1 heures au-dessus de l'irradiance extraterrestre ».
Aucun S1 neuf.

## 4. Ce qui est bien (à ne pas casser)
- Étape Toit en mode guidé : fidèle à la maquette Main (tuiles, Longueur/Largeur avec « m », champ qui garde « 12,5 »), et en sombre fidèle à ToitSombre (fonds bleu nuit, accents or).
- Poignées 3D à la hauteur du toit : glisser un coin déplace bien ce coin (ACAL1185).
- Exports : glTF (5 instances de module = 5 panneaux, aucun prix), KML (1 pan + 5 modules, lng/lat), PNG « sur photo » à la bonne place.
- Lecture de la pente sur un relief GeoTIFF : suggestion 20 °, aucun appel IGN, jamais recopiée dans la pente du pan.
- Contrôle d'échelle du plan importé (« ×10 ») et qualité de la météo déposée (59,9 min pour un décalage de 60) : justes et sans verdict.
- Le refus de modification des pans verrouillés et le refus de pivoter avec des panneaux posés parlent clairement.

## 5. Non essayé / réserves de preuve
- ACAL507 : le géocodeur MapTiler répond 403 sur cette pile (clé factice) ; la preuve a été jouée en simulant sa réponse par interception (lignes, non-échange automatique, centrage OK). Avec le vrai 403, une seule ligne reste, sans message d'erreur.
- ACAL531 : aucune clé d'IA ; l'API de détection a été simulée par interception ; le comportement de l'écran (cases, DEVINE, bandeau « Compte NON engageable ») est réel.
- ACAL508 : avec un vrai jeton Mapbox (France puis Maroc) non joué ; verdict `non-fait` fondé sur le fait que l'atelier ERP ne transmet jamais `imagery` (lecture de `useAtelierBoot.js`) — à rejouer si l'orchestrateur dispose d'un jeton.
- ACAL515 : état « site sans panneau posé » inatteignable à la main (pose automatique à la fermeture du contour).
- ACAL536 : pas de lecteur Google Earth ; structure du fichier lue directement. ACAL529 : l'exactitude au pixel des 4 coins n'a pas été mesurée.
- ACAL764 : la ligne « non calculé — motif » (épingle absente) n'a pas été jouée.
- À vérifier : chaque enregistrement déclenche un `POST …/simuler/` qui répond 409 (corps non lu) ; session expirée (401) après environ 25 minutes.

## 6. Trois propositions les plus fortes
1. **Une seule source de vérité pour la liste des obstacles** (PVsyst « Near shadings » / OpenSolar « Objects » : la liste se met à jour à chaque pose) : redessiner `#rp9-objets-site` à chaque pose, annulation et ouverture, et ne plus dépendre d'un changement de pan.
2. **Une seule numérotation des pans** (OpenSolar « Roof planes » : « Pan 1, Pan 2 » partout) : la même étiquette dans la liste, la barre d'état, l'aria-label et le document, et une étiquette « Existant 2019 » dans la ligne.
3. **Un mode Expert qui se voit tout de suite** (Aurora Solar : la bascule de niveau change l'écran sans rechargement) : un seul état partagé pour Guidé/Expert, et des champs/tiroirs expert qui reprennent les jetons de l'ERP (bordures, fonds, cibles) au lieu de classes héritées du site public.
