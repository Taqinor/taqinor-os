# Audit de 37 verdicts `ok` du tour 2 (relecteur adverse AUDIT-OK, 23/11)

Échantillon : `T2/cv/ECHANTILLON-OK.md`. Lignes : `registre/evenements/T2-audit-ok.jsonl`. Méthode : texte complet de la tâche, ligne de verdict du relecteur, capture ouverte (et ses voisines du même dossier) ; DXF et SVG relus par un lecteur indépendant.

**Comptes : confirmé 17 · insuffisant 16 · contredit 4. Mal prouvés : 20 sur 37, soit 54 %.**

| Relecteur | conf. | insuf. | contr. | | Relecteur | conf. | insuf. | contr. |
|---|---|---|---|---|---|---|---|---|
| F2-CONSO | 1 | 1 | 0 | | F2-RESU | 1 | 2 | 0 |
| F2-DOCS-a | 2 | 0 | 0 | | F2-RESU-b | 0 | 2 | 0 |
| F2-DOCS-b | 0 | 1 | 1 | | F2-SIMU-a | 1 | 1 | 0 |
| F2-ELEC-a | 1 | 1 | 0 | | F2-TOIT-a | 1 | 1 | 0 |
| F2-ELEC-b | 0 | 3 | 0 | | F2-TOIT-b | 2 | 0 | 0 |
| F2-GESTES | 1 | 1 | 0 | | S2-PARCOURS | 1 | 0 | 2 |
| F2-GESTES-b | 0 | 1 | 1 | | S2-PARCOURS-b | 1 | 1 | 0 |
| F2-POSE-a | 2 | 0 | 0 | | T2 | 2 | 0 | 0 |
| F2-POSE-b | 1 | 1 | 0 | | | | | |

## Contredits (4)
- **ACAL832** (F2-DOCS-b) : `r1976-p14.png` imprime une consommation annuelle de 121 976,8 kWh, alors que le même rapport donne 12 197,68 : c'est dix fois trop (constat T2-F2-RESU-b-011).
- **ACAL987** (F2-GESTES-b) : `s20_out2.txt` relève un 409 sur plan-importe et un console.error à l'ouverture de 15 onglets ; la spec e2e n'a pas été lancée.
- **ACAL1285** (S2-PARCOURS) : `s36-etape-Resultats.png` et `s36-etape-Documents.png` n'ont pas le cadre « Étape N sur 5 », ni le bouton de pied ; une maquette plus récente l'a peut-être remplacé, à arbitrer.
- **ACAL853** (S2-PARCOURS) : sur `F2-CONSO/cap/c10-carte.png` (un seul pan, devis lié), la carte Recommandation dit 14 620 kWh/an et la carte Total 11 611 ; la capture citée ne montre aucune des deux cartes.

## Insuffisants (16)
- **Un seul des cas exigés est joué**, souvent avec l'aveu du relecteur dans « reste » : ACAL847 (moitié « sans le droit »), ACAL831 (verrou), ACAL664 (50 °C ⇒ 90 %), ACAL706 (motif d'une requête impossible), ACAL757 (sans courbe de charge), ACAL754 (refus 409 `acces_modules`), ACAL761 (bloc « usages » jamais rendu avec des valeurs), ACAL863 (cheminée), ACAL1305 (clauses « seulement si servi »), ACAL934 (verdict_de_conception non lu).
- **La capture montre un autre état que celui annoncé** : ACAL1188 (« avant » est déjà « Conforme », « après » est le panneau Toit), ACAL636 (aucune section de câble), ACAL993 (atelier au lieu de la réponse réseau), ACAL569 (onglet en chargement), ACAL925 (la cible « 4 » n'est pas visible).
- **Valeur exigée non montrée** : ACAL493 (l'ombre à 1,2 m n'est comparée qu'à 3 m, jamais à l'état sans hauteur).

## Conclusion
54 % des `ok` de l'échantillon sont mal prouvés (43 % insuffisants, 11 % contredits). Il ne faut donc cocher aucun des 189 `ok` sur la foi du verdict seul : les 17 confirmés de l'échantillon peuvent l'être, les autres demandent un rejeu ciblé.

Écarts concentrés chez F2-ELEC-b (3 sur 3), F2-RESU-b (2 sur 2), F2-DOCS-b (2 sur 2), F2-GESTES-b (2 sur 2), S2-PARCOURS (2 contredits sur 3) et F2-RESU (2 sur 3). Sans écart : F2-DOCS-a, F2-POSE-a, F2-TOIT-b et T2 (2 sur 2 chacun).

Cause dominante : un `ok` donné alors que le relecteur écrit lui-même dans « reste » qu'un cas exigé n'est pas joué, ou qu'une valeur est fausse (7 tâches).
