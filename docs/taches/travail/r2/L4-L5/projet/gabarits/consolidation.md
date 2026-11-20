# Consolidation du tour <n> — <périmètre> (go-deep L4 / L5)

<Bloc d'ancrage de CLAUDE.md, mot pour mot.>

Entrées : `registre/constats/T<n>-*.jsonl`, les rapports `T<n>/*.md`, le contrat `contrat-de-sortie.md`, le code de
`<branche>@<sha9>` (la tête que les relecteurs ont eue sous les yeux) lu dans `<worktree en lecture>`.
Sorties : (1) les événements `consolidation` au registre, un par constat ; (2) les fiches `fiche-invariant.md` des
classes ; (3) les corrections inscrites au plan du propriétaire ; (4) CE fichier, 100 lignes au plus — le détail
vit dans le registre et le plan, pas ici.

Vocabulaire fixe : cause « lue » (ligne ouverte dans cette session, ancre `fichier::symbole`) · « probable » (déduite
du code, sans mesure) · « à reproduire » (introuvable). Jamais d'ancre `fichier:ligne` (METHODE anti-pattern 11).
Gravité et axes : `registre.md`. Choix tranchés : règle des Tensions 3 de la skill.

## § 0. Classes de défaut (une CONCEPTION par classe, pas symptôme par symptôme)
Une classe = un comportement racine derrière ≥ 2 constats (ce tour ou les précédents : chercher dans le registre).
| Classe | Invariant (une phrase) | Constats | Fiche | Endroits violables (nb, commande de grep) | Test premier (qui l'écrit) |
|---|---|---|---|---|---|
| K-<nom> | « <…> » | T<n>-…, … | `classes/K-<nom>.md` | <n> — `git grep -n "<motif>" <sha> -- <chemins>` | test-writer, branche `tests/T<n>` |

## § 1. Corrections retenues (A d'abord), rangées par lane
Une ligne par correction ; le texte complet (cause, preuve attendue, fichiers) est la tâche du plan.
| Correction | Constats | Gravité | Cause (statut) | Preuve attendue | Fichiers | Tâche du plan | Lane |
|---|---|---|---|---|---|---|---|

## § 2. Écartés ou reclassés (chaque verdict est au registre)
| Constat | Verdict (`doublon` · `ecarte-artefact` · `ecarte-hors-perimetre` · `ecarte-faux` · `a-reproduire`) | Raison en une ligne, preuve |
|---|---|---|

## § 3. Choix de produit tranchés
Règle (sans consigne contraire : NEUF / MIXTE → lot de questions du tour 0 ; EXISTANT ou « aucune question » → règle
écrite) : le plus simple pour l'utilisateur, sinon la maquette, sinon ce que font les références nommées.
| # | Choix | Options | Retenu | Règle appliquée | Coût si faux | Réversible par |
|---|---|---|---|---|---|---|
Jamais enregistrés comme décisions de Reda ; redits au rapport final.

## § 4. Lanes
1. **Lane 0 — changement de contrat global** (s'il y en a un : code d'erreur, forme partagée, API d'un composant
   partagé) : SEULE, pliée et verte avant le départ des autres, avec la table « ce qui change, qui le lit ».
2. **Lanes de correction** : sortie de `python scripts/plan_lanes.py <plan du propriétaire>` après inscription des
   tâches (`@lane`, `@files`, `@model`, `@after`) — collée ici telle quelle, avec le modèle de chaque lane ; aucune
   table fichier → lane écrite à la main.
3. **Interfaces entre lanes** écrites noir sur blanc (prop, événement, forme d'API, contrat d'abord) ; toute
   dépendance = `@after`.
4. **Lane de couture** : `@after` toutes les autres, seule sur l'arbre ; rejoue les specs e2e contre le build
   assemblé et parcourt chaque écran.
5. Fichiers à propriétaire unique écrits en dernier (lexique, références) : nommer la lane qui les possède.

## § 5. Compte
Vus <n> · retenus <n> (A <a>, B <b>, C <c>) · doublons <n> · écartés <n> (par relecteur et par axe : sortie du script
de `registre.md` § 5) · classes <n> · corrections <n> · tâches de plan <n> · lanes <n>. Contre-vérification du tour
précédent : ok <n> · partiel <n> · non-fait <n> · faux <n> · régression <n> · déjà-présent <n>.
