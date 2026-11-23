# Audit des `ok` — lot D-2 (rattrapage RATT-1, RATT-2 et un B2), tour 2, 23/11

Liste : `T2/cv/AUDIT-OK-D-2.md` (19 verdicts, tous joués dans l'ordre). Lignes : `registre/evenements/T2-audit-ok-D-2.jsonl`.
Méthode : texte complet de la tâche, ligne de verdict, réserves du rapport, captures ouvertes (et leurs voisines), plus les fichiers
du relecteur quand ils tranchent (res2018.json, res-2026/2027.json, export2018.xlsx, r2026.pdf, relevés texte d'écran).

**Comptes : confirmé 7 · insuffisant 11 · contredit 1. Mal prouvés : 12 sur 19.**

| Relecteur | confirmé | insuffisant | contredit |
|---|---|---|---|
| RATT-1 | 5 (ACAL880, 888, 894, 897, 856) | 8 | 0 |
| RATT-2 | 2 (ACAL833, 740) | 3 | 1 |
| B2 | 0 | 1 | 0 |

## Contredit (1)
- **ACAL444** (RATT-2) : la ligne dépliée « Reflet sur la vitre » (`d-2019-a-2-deplie.png`, `d-2019-m-2-deplie.png`) n'a pas d'« Entrée », alors que l'étape iam en sert une. `CascadePertesLignes.jsx` (l. 51) n'affiche l'entrée que si c'est une chaîne. Or toutes les étapes calculées la servent en objet : aucune ligne ne la montre jamais. Les énergies avant/après sont coupées sur les deux captures.

## Insuffisants (11)
- **ACAL877** : les « ? » de « m³ mensuels » et « couverture » ne sont jamais vus (pas de pompe chiffrée, pas de tableau mensuel). La phrase de `volumes_omis` n'est pas lue.
- **ACAL879** : les deux captures montrent le panneau Toit. Seuls les relevés texte prouvent « Non calculé » et la source métier. À arbitrer : la même vérification s'affiche « Non vérifiable » d'un côté, « Non calculé » de l'autre.
- **ACAL878** : la moitié Documents/Dossiers n'est pas jouée (réserve du relecteur).
- **ACAL885** : la Voc à froid « de l'écran » n'est jamais comparée, faute d'écran qui l'affiche (réserve). La feuille seule est juste (672,2 V).
- **ACAL959** : la preuve passe par l'API seule. La section Matériel électrique de la copie n'est pas capturée (`t959.png` = panneau Toit).
- **ACAL874** : l'élévation, la marge, les chutes et les tronçons ne citent pas de valeur servie (« valeur non publiée % »), réserve du relecteur.
- **ACAL883 / ACAL884** : la branche « réglages différents ⇒ différences nommées » n'est pas jouée. C'est le « fini quand » même (réserve du relecteur).
- **ACAL767** : l'export n'a jamais été appelé. Le cas « export refusé sans toast » n'est pas exercé.
- **ACAL738** : le cas « sans p_dc_kw ⇒ deux repères + phrase du manque » n'est pas joué (réserve du relecteur).
- **ACAL435** (B2) : la ligne de verdict n'a pas de preuve écrite et aucun tangage ni cap n'est relevé. « Face » égale « Sud » (pan plein sud). Rien ne montre la transition douce.

## Remarques
- Les réserves écrites par RATT-1 sur ses `ok` (ACAL874, 878, 883/884, 885) touchent toutes un cas exigé : elles font chacune un `insuffisant`. La réserve sur ACAL894 (« PVGIS a répondu ») est hors du « fini quand » : confirmé.
- Trois captures de RATT-1 citées comme écrans électriques (`t879-*`, `t885-electrique`, `t959`) montrent en fait le panneau Toit.
- ACAL880 : confirmé sur l'état capturé, rangé par perte décroissante. Le `res2018.json` de 07:03 vient d'une autre simulation et classerait autrement (dispersion d'ombrage et échauffement passeraient devant) : rien de contredit.
