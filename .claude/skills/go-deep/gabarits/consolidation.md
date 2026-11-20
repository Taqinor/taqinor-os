# Consolidation du tour <n> — <périmètre> (go-deep L4 / L5)

<Bloc d'ancrage de CLAUDE.md, mot pour mot.>

Entrées : `registre/constats/T<n>-*.jsonl`, `registre/evenements/*.jsonl` (verdicts du tour, demandes croisées), les
rapports `T<n>/*.md`, le contrat `contrat-de-sortie.md`, le code de `<branche>@<sha9>` (la tête que les relecteurs ont
eue sous les yeux) lu dans `<worktree en lecture>`.
Sorties : (1) TON fichier `registre/evenements/T<n>-consolidation.jsonl`, un événement par constat, et
`registre/classes.jsonl` — tu es leur seul écrivain ; (2) les fiches `fiche-invariant.md` des classes ; (3) les
corrections inscrites au plan du propriétaire, AU FORMAT DE CE PLAN (§ 1) ; (4) CE fichier, 100 lignes au plus — le
détail vit dans le registre et le plan, pas ici.

Vocabulaire fixe : cause « lue » (ligne ouverte dans cette session, ancre `fichier::symbole`) · « probable » (déduite
du code, sans mesure) · « à reproduire » (introuvable). Jamais d'ancre `fichier:ligne` (METHODE anti-pattern 11).
Gravité S1-S4 et axes : `registre.md`. Choix tranchés : Tensions 3 de `L4.md`.

## § 0. Classes de défaut (une CONCEPTION par classe, pas symptôme par symptôme)
Une classe = un comportement racine derrière ≥ 2 constats (ce tour ou les précédents : chercher dans le registre).
| Classe | Invariant (une phrase) | Constats | Fiche | Endroits violables (nb, commande de grep) | Matrice (champs × conditions) | Test premier (lane) |
|---|---|---|---|---|---|---|
| K-<nom> | « <…> » | T<n>-…, … | `classes/K-<nom>.md` | <n> — `git grep -n "<motif>" <sha> -- <chemins>` | <n> × <m> cases | `tests/T<n>-<lane>` |
Chaque classe ouverte est donnée en CIBLE aux relecteurs du tour suivant (leur brief, « Classes ouvertes »).

## § 1. Corrections retenues (S1-S2 d'abord), rangées par lane
Où elles s'inscrivent : dans le plan du PROPRIÉTAIRE des fichiers (`check_ownership.py --owner-of`), au format de ce
plan, jamais un format inventé :
- plan de domaine (`docs/plans/PLAN_<X>.md`, ex. `PLAN_TACHES.md`) → tâches d'une ligne `@lane @files @model @after` ;
- plan d'audit (`docs/plans/PLAN_AUDIT_*.md`) → tâches v3 complètes (METHODE §C.2 : les 14 clauses, `@model`
  obligatoire ; `check_taches_cablage.py` est bloquant) ; `Files:` sur plusieurs propriétaires →
  `PLAN_AUDIT_TRANSVERSE.md` avec `(@atomique: …)` ;
- avant de pousser : `check_ownership.py`, `check_ancres_taches.py`, `check_taches_cablage.py` (METHODE §C.4.5).
Un tour de plus de ~80 corrections se découpe en VAGUES (WOW23, `plan_lanes.py --wave-size 80`), chacune mergée dès
sa CI verte ; jamais une seconde vague sur une rouge.
| Correction | Constats | Gravité | Cause (statut) | Preuve attendue | Fichiers | Tâche du plan | Lane | Vague |
|---|---|---|---|---|---|---|---|---|

## § 2. Écartés ou reclassés (chaque verdict est dans ton fichier d'événements)
| Constat | Verdict (`doublon` · `ecarte-artefact` · `ecarte-hors-perimetre` · `ecarte-faux` · `a-reproduire`) | Raison en une ligne, preuve |
|---|---|---|

## § 3. Choix de produit tranchés
Règle (sans consigne contraire : NEUF / MIXTE → lot de questions du tour 0 ; EXISTANT ou « aucune question » → règle
écrite) : le plus simple pour l'utilisateur, sinon la maquette, sinon ce que font les références nommées.
| # | Choix | Options | Retenu | Règle appliquée | Coût si faux | Réversible par |
|---|---|---|---|---|---|---|
Jamais enregistrés comme décisions de Reda ; redits au rapport final. Une réponse de Reda va dans
`docs/audits/decisions.yml` ou `docs/claude-memory/`, dans la PR du tour.

## § 4. Lanes
1. **Lane 0 — changement de contrat global** (s'il y en a un : code d'erreur, forme partagée, API d'un composant
   partagé, ou un rouge / un angle mort lu au tour 0 sur le dernier run de CI de `main`) : SEULE, pliée et verte avant le départ des
   autres. Elle possède le serveur ET tous ses lecteurs trouvés par grep (client d'API, mocks, specs e2e), même dans
   des fichiers d'autres lanes ; elle livre la table « ce qui change, qui le lit » ; les lanes en vol la reçoivent et
   se rebasent.
2. **Lanes de correction** : quand les corrections sont des tâches de plan avec `Files:`, sortie de
   `python scripts/plan_lanes.py <plan du propriétaire>` collée telle quelle, avec le modèle de chaque lane ; sinon (ou
   si la sortie unit tout en une lane surdimensionnée ou refuse des tâches) la table fichier → lane ci-dessous,
   vérifiée disjointe, et le dire au rapport.
   | Fichier | Lane | Modèle |
   |---|---|---|
3. **Identifiants partagés** (classe CSS, prop, `data-*`, code HTTP, événement) — un propriétaire chacun ; la lane de
   couture les greppe des deux côtés.
   | Identifiant | Type | Propriétaire (lane) | Lecteurs (lanes, fichiers) |
   |---|---|---|---|
4. **Interfaces entre lanes** écrites noir sur blanc (prop, événement, forme d'API, contrat d'abord) ; toute
   dépendance = `@after`.
5. **Lane de couture** : `@after` toutes les autres, seule sur l'arbre assemblé et poussé ; greppe chaque identifiant
   partagé des deux côtés, PARCOURT chaque écran sur l'instrument, prend et regarde la capture « après » de chaque
   correction visible avec les gestes écrits par sa lane, répond aux demandes croisées.
6. Fichiers à propriétaire unique écrits en dernier (lexique, références) : nommer la lane qui les possède.

## § 5. Compte
Vus <n> · retenus <n> (S1 <a>, S2 <b>, S3 <c>, S4 <d>) · doublons <n> · écartés <n> (par relecteur et par axe : sortie
du script de `registre.md` § 6) · classes <n> · corrections <n> · tâches de plan <n> · lanes <n> · vagues <n>.
Contre-vérification du tour précédent : ok <n> · partiel <n> · non-fait <n> · faux <n> · régression <n> ·
déjà-présent <n>. Demandes croisées ouvertes : <n>.
