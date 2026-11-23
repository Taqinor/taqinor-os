# Relecture adverse des `ok` du tour 3 (AUDIT-OK-T3)

64 `ok` relus : les 61 de `T3/cv/AUDIT-OK-T3.md` + 3 ajoutés depuis par T3-ELEC (ACAL1414, 1704, 1338).
Chaque capture citée a été ouverte ; verdicts ligne à ligne : `registre/evenements/T3-audit-ok.jsonl`.

| Vérificateur | confirme | insuffisant | contredit |
|---|---|---|---|
| T3-POSE | 6 | 4 | 0 |
| T3-PROD | 10 | 3 | 0 |
| T3-ECRANS | 7 | 1 | 0 |
| T3-ELEC | 18 | 1 | 2 |
| T3-TOIT | 7 | 5 | 0 |
| **Total** | **48** | **14** | **2** |

## Contredits
- **ACAL1712** (ELEC) : `plan1948-p1.png`, cotes justes (S 2,29 / E 0,11), mais coin NO toujours tassé (« 0,00 m », N, « 0,00 m », O), cote verticale sur le bord de la feuille, « 0,11 m » sur la lettre E.
- **ACAL1704** (ELEC) : `d7-docs.png`, « Fiche incomplète : … (Vmp) du module » est lu, mais le bouton dit « Régler dans Électrique », pas le geste exigé « Compléter la fiche du module ».

## Insuffisants (ce qui reste à rejouer)
- **ACAL1520** (POSE) : bandeau du mode « Déplacer » à 3,55 kWc absent de `x1-actif.png` (lu au DOM seulement).
- **DC-8** (POSE) : fenêtre de production « 3,55 kWc · 5 × 710 W » non capturée.
- **DC-1** (POSE) : note « 3 châssis de 2 × 10 posés » et pose de 60 absentes de `ch2-note.png` / `ch2-full.png`.
- **ACAL1438** (POSE) : `ui2-avance-expert.png` a le panneau Avancé fermé ; glTF et Vidéo 10 s jamais visibles après le clic Expert.
- **ACAL1607** (PROD) : cas à Uc (fiche NOCT + Uc) non joué ; seul le chemin NOCT sans Uc est prouvé (`D1-resultats-guide.png`).
- **ACAL1606** (PROD) : seule l'IAM est exclue (thermique omise) ; exclusion de la chaleur à rejouer sur un pan à thermique appliquée (ex. 2043).
- **ACAL1702** (PROD) : `P1-documents-perime.png` est pris en « Modifications non enregistrées » avec le toast « serveur n'a pas répondu » ; la note de calcul disparaît, donc « même règle que la note » n'est pas visible.
- **ACAL1428** (ECRANS) : écriture de pitchSource au prochain « Enregistrer » non relue (`s32-confirmer.png`).
- **ACAL1333** (ELEC) : API seule ; la carte de la liste « ⚠ N points à régler » et l'état « à relire » ne sont pas capturés.
- **ACAL1405** (TOIT) : hauteur 6,0 m, provenance et note absentes de `s1-relu-env.png` / `s1-relu-haut.png`.
- **ACAL1406** (TOIT) : accès solaire avant/après (99,6 %) non capturé.
- **ACAL1430** (TOIT) : liste, cadenas et message de verrou du cas « 2 pans » non capturés (`s26-site.png` = un autre calepinage).
- **ACAL1431** (TOIT) : liste des pans « Zone 1 · Existant 2019 » non capturée (seul le tableau Site l'est).
- **ACAL1420** (TOIT) : tableau « Site » à 87 m² absent de `s34-site.png` (seule la surface du panneau Toit).

Remarques hors verdict : les preuves API de T3-ELEC citent des scripts, pas des réponses enregistrées. Je les ai jugées
sur la preuve écrite et j'ai revérifié les clés de contrat au commit `f7d5f1a7ec` (schéma, `calepinage_publication.json`,
`test_acal_liste_forme.py`, grep « onglet Production »).
