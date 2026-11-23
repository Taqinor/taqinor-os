# Audit des `ok` du lot B (pose des panneaux et électrique), tour 2, relecteur AUDIT-OK-B, 23/11

Liste : `T2/cv/AUDIT-OK-B.md`, 32 verdicts relus en entier. Lignes : `registre/evenements/T2-audit-ok-B.jsonl`. Méthode :
le texte complet de la tâche, la ligne de verdict, le rapport du relecteur, la capture citée et ses voisines, plus les
scripts et sorties conservés dans le scratchpad (`dl/`, `*.json`, `t*.js`).

**Comptes : 23 confirmés · 9 insuffisants · 0 contredit. 28 % des `ok` sont mal prouvés.**

| Relecteur | confirmé | insuffisant | contredit |
|---|---|---|---|
| F2-POSE-a | 4 | 3 | 0 |
| F2-POSE-b | 1 | 4 | 0 |
| F2-ELEC-a | 4 | 0 | 0 |
| F2-ELEC-b | 14 | 2 | 0 |

## Insuffisants (9) : ce qu'il reste à rejouer
- **ACAL607** (F2-POSE-a) : `s12-C-site-table.png` coupe le tableau Site avant la colonne kWc, et aucune sortie DOM n'est conservée. Il reste à capturer, sur le calepinage 1962, le tableau défilé jusqu'à la colonne kWc : ligne Champ au sol à 124,96 kWc, total additionné.
- **ACAL572** (F2-POSE-a) : la section lestage partait vide (`param-avant.json` : `{}`), donc « zones de vent intactes » n'est pas jouée. Il reste à saisir la bande de rive alors que `zones` et `zone_par_defaut` sont déjà réglées, puis à relire GET parametres/.
- **ACAL579** (F2-POSE-a) : `s32-A-pieds-comparaison.png` joue 5 modules au pas de 1,32 m (6 pieds → 4). Il reste le cas du fini quand : 12 modules au pas de 1,15 m avec une portée de 2,4 m (7 triangles au lieu de 13), et la visionneuse client, qui doit garder 13 triangles.
- **ACAL561** (F2-POSE-b) : l'enregistrement « égout 0,40 / notice X » est relu (`t20-recharge.png`). Il reste le refus du serveur pour une valeur sans source, qui doit nommer `degagements.retraits_par_arete[0].source`.
- **ACAL549** (F2-POSE-b) : `t22-H.png` ne montre pas la phrase de cause, `motifsPansVides` n'est jamais lue et le cas joué est 2 × 1 m à 0,50 m. Il reste le pan de 3 × 1,5 m à 0,80 m, avec une capture de la phrase et une lecture de la clé dans GET layout/.
- **ACAL593** (F2-POSE-b) : l'ancre de 2 m revient bien avec son cercle (`t27-recharge.png`), mais seul un rayon de -1 a été essayé. Il reste le refus d'un rayon vide sous le champ.
- **ACAL566** (F2-POSE-b) : un lead « tuiles » reçoit bien le système « tuiles » (`t52-fixation.png`). Il reste le cas de doute : deux systèmes déclarent « tuiles », et le refus doit lister ces deux-là seulement.
- **ACAL642** (F2-ELEC-b) : `v642-affectation-u.png` ne montre aucune chaîne, et la preuve ne donne que des ensembles sur un pan de 3 × 6. Il reste un pan de 2 × 10 en motif u, avec l'ordre lu dans la chaîne (1-10 puis 20-11), et le défaut comparé à l'ordre d'avant.
- **ACAL678** (F2-ELEC-b) : l'alerte avec la limite à 3 m² est vue (`v678-limite3.png`). Il reste à vider la limite et à constater qu'aucune alerte de boucle n'apparaît dans l'onglet Affectation des chaînes.

## Points notés sans changer le verdict
- ACAL685 : le relecteur écrit « limite absente non rejouée », mais `v685-sanslimite-ouvert.png` montre « limite non saisie : réglage `boucle_dc_max_m2` ». Confirmé.
- ACAL827 et ACAL887 : le serveur rend 409 là où la tâche écrit 400 (kW et A saisis ensemble ; mois en double). C'est hors du fini quand : un écart à signaler, pas un défaut du fini quand.
- ACAL548, ACAL632, ACAL782 et ACAL783 ont été prouvées sur d'autres valeurs que celles de la tâche (seuil de 98 au lieu de 80, pans de 9 modules, 14,2 kWc, 87,9 %). Le résultat exigé par le fini quand y est atteint, d'où le confirmé. Pour ACAL579, au contraire, les nombres attendus eux-mêmes (7 contre 13) ne sont pas montrés.

## Conclusion
F2-ELEC-a (4 sur 4) et F2-ELEC-b (14 sur 16) tiennent sur ce lot. F2-POSE-b est le plus faible : 4 `ok` sur 5 laissent un cas exigé non joué. Cause dominante (7 sur 9) : la seconde moitié du fini quand (refus, cas vide, cas de doute, limite vide) n'est pas jouée, et le relecteur l'écrit souvent lui-même dans « reste ».
