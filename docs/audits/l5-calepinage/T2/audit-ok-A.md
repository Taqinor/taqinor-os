# Audit des verdicts `ok` du tour 2 — lot A (toit et gestes de dessin), relecteur adverse AUDIT-OK-A, 23/11

Liste : `T2/cv/AUDIT-OK-A.md` (35 verdicts, tous joués dans l'ordre). Lignes : `registre/evenements/T2-audit-ok-A.jsonl`.
Méthode : texte complet de la tâche, ligne de verdict du relecteur, capture citée et ses voisines ouvertes ; .glb, .kml et
la spec ACAL478 relus directement.

**Comptes : confirmé 22 · insuffisant 13 · contredit 0. Mal prouvés : 13 sur 35, soit 37 %.**

| Relecteur | confirmé | insuffisant | contredit |
|---|---|---|---|
| F2-TOIT-a | 1 | 8 | 0 |
| F2-TOIT-b | 8 | 2 | 0 |
| F2-GESTES | 8 | 1 | 0 |
| F2-GESTES-b | 5 | 2 | 0 |

## Insuffisants (13) — ce qu'il reste à rejouer
- **ACAL1292** (TOIT-a) : montrer où vivent les rangées angle/aimantation/grille dans « Avancé » (s38-avance.png ne les porte pas, s05-expert.png les garde sous la carte) et donner le verdict FIDÈLE que la preuve exige (constat -018 dit PROCHE).
- **ACAL498** (TOIT-a) : capture du menu relu pour climatiseur et citerne (s19-relu.png ne montre qu'« Exutoire de fumée ») et lecture de la traduction moteur CLIMATISEUR / NATURE_INCONNUE.
- **ACAL496** (TOIT-a) : refus joué sans date NI heure seulement ; rejouer date sans heure, puis heure sans date.
- **ACAL497** (TOIT-a) : la note de perte annuelle exigée en capture est hors cadre (s22-ombre-*.png) ; sa valeur −72 % est mise en doute par -011 / -014.
- **ACAL499** (TOIT-a) : modules reculés de 1,8 m non mesurés (aveu du relecteur) ; phrase « recul de base » de la citerne absente des captures.
- **ACAL449** (TOIT-a) : cas « document sans table : ligne table d'ombrage absente » non joué ; légende des bornes illisible (s46-diagramme.png).
- **ACAL458** (TOIT-a) : refus d'une ligne illisible / d'un tour incomplet non joué.
- **ACAL466** (TOIT-a) : s50-utiliser.png = s50-relief.png, le champ Pente du terrain rempli n'est pas montré ; pente lue à l'épingle, pas sur les sommets du champ.
- **ACAL529** (TOIT-b) : écart des 4 coins de calage < 1 px non mesuré ; sur calepinage-1972-sur-photo.png les rangées débordent du toit.
- **ACAL764** (TOIT-b) : ligne « non calculé — épingle du site absente » non jouée.
- **ACAL949** (GESTES) : Alt + molette sur un fond calé non joué (pas d'imagerie) ; caler un plan importé en fond suffit.
- **ACAL962** (GESTES-b) : moitié « société au pays ma » non jouée.
- **ACAL967** (GESTES-b) : statut « Calepinage (copie) chargé. » dans aucune capture (s22-copie-statut.png en « Chargement… »).

## Contredits
Aucun : aucune capture ne montre le « fini quand » violé.

## Lecture
- Écart concentré chez **F2-TOIT-a (8 sur 9)** : `ok` donnés sur une moitié de « fini quand », souvent avec l'aveu dans « reste », et captures coupées ou en double.
- F2-TOIT-b, F2-GESTES et F2-GESTES-b tiennent à 21 sur 26 ; leurs écarts sont un second cas non joué, déjà écrit dans « reste ».
- Remarques non bloquantes : ACAL507 joué avec un géocodeur simulé par interception (écran réel, vrai 403 aussi vu) ; ACAL914 cite 40,26 / 39,76 kWc alors que sa capture montre 36,00 / 35,50 (même refus).
