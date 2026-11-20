# R3 — tri de l'orchestrateur (20/11/2026) : ce que le correcteur applique

Trois rapports : `rejeu.md` (2 bloquants, 11 importants), `maison.md` (3 bloquants, 12 importants), `faits.md`
(0 bloquant, 6 importants, 8 optionnels). Chaque ligne ci-dessous est une DÉCISION : l'appliquer telle quelle ; le
détail et le texte proposé sont dans le rapport cité. Ce qui n'est pas listé ici n'est pas à faire.

## D0 — Structure (décision de l'orchestrateur, pas d'un vérificateur)
La skill est chargée à CHAQUE « go deep » : un L1 ne doit pas payer le texte de L4 et L5. Découper :
- `SKILL.md` : régime (court), choix du niveau, squelette L1-L3, tableau des niveaux, garde-fous communs, non
  négociables, et pour L4 / L5 un RÉSUMÉ de 10-15 lignes chacun + « lis `L4.md` / `L5.md` avant de commencer ».
  Cible : ≤ 170 lignes.
- `L4.md` : la procédure complète de L4 (tour 0 → rétro), ses garde-fous de coût et d'instrument, les tensions tranchées.
- `L5.md` : ce que L5 ajoute.
- `gabarits/` : inchangé dans son principe. `conception.md` : sources et choix (issu de `notes-de-conception.md`).
Les fichiers frères d'une skill sont le mécanisme officiel (divulgation progressive) ; aucun précédent dans ce dépôt :
le dire dans `conception.md`.

## Bloquants
- **rejeu B1** — registre : UN fichier d'événements PAR ÉCRIVAIN (`evenements/<role>-<id>.jsonl` : chaque relecteur,
  la consolidation, chaque lane), jamais l'orchestrateur qui recopie de la prose ; le script lit `evenements/*.jsonl`.
- **rejeu B2 + faits 3 + faits 4** — plafond de coût, UNE seule règle cohérente : k compte TOUS les tours, le dernier
  compris ; la vérification finale ciblée + la critique du diff serveur ont une réserve à part, TOUJOURS jouées ;
  supprimer le seuil « pas de tour à u ≥ 65 » (redondant et incohérent avec la formule) ; coût par tour recalé sur ce
  que la rétro § 3 mesure vraiment (dis d'où vient chaque nombre) ; toute la formule étiquetée « valeurs de départ, non
  calibrées : à recaler après le premier L4 lancé depuis la skill ». Même étiquette pour : 10 % / 25 % de contre-
  vérification, 3 tentatives du disjoncteur, 30 min / 5 jours, les seuils K du contrat, 20 % / 80 % du régime.
- **maison C1** — crochet : reprendre la correction prototypée et testée par le vérificateur (verbes réduits à go / do /
  lance / fais ; relever TOUS les niveaux cités ; dès que deux niveaux différents sont cités, ou qu'une négation /
  question précède, texte NEUTRE qui ne lance ni L4 ni L5 et dit « lis la phrase de Reda »). Rejouer sa table de 29
  phrases + les 40 du projet : zéro déclenchement L4 / L5 à tort.
- **maison C2** — où vont les corrections : dans le plan du PROPRIÉTAIRE, AU FORMAT DE CE PLAN. Plan de domaine
  (`docs/plans/PLAN_<X>.md`, ex. PLAN_TACHES : c'est ce que la session a fait, CI verte) → tâches d'une ligne. Plan
  d'audit (`PLAN_AUDIT_*.md`) → tâches v3 complètes (les 14 clauses, `check_taches_cablage.py` est bloquant) ou le
  plan transverse. Jamais un format inventé.
- **maison C3** — instrument : rendre l'interdit IMPOSSIBLE, pas « déconseillé ». Jamais `--env-file` du vrai `.env`
  (la session du 19/11 l'a fait : constat confirmé par l'orchestrateur, `lancer-django.sh` l. 12) ; liste des
  variables FORCÉES à vide ou à une valeur morte (celle du rapport) ; écoute sur 127.0.0.1 seulement ; pas de réseau
  partagé avec la pile d'une autre session quand un service à clés réelles y est joignable ; un CONTRÔLE de tour 0
  (commande donnée dans le gabarit) qui lit l'environnement du conteneur et ARRÊTE le tour 0 si une clé réelle, un
  backend d'envoi réel ou une écoute publique est trouvé.

## Importants — maison
- **I1 + rejeu I9** — un tour de plus de ~80 corrections se découpe en VAGUES (WOW23), chacune mergée dès sa CI verte.
  Conséquence dite à Reda à chaque merge : « n corrections pas encore contre-vérifiées : déployer maintenant ou après
  le tour suivant » (le deploy est son geste ; la session du 19-20/11 aurait mis 3 régressions sur `main` au tour 1).
- **I2 + I3** — lanes : eslint + flake8 / py_compile + LE test qu'elles réparent ; pas de Docker, pas de suite voisine,
  pas de build + Playwright complet par lane avant la poussée. La preuve d'une correction VISIBLE reste : une capture
  « après » sur l'instrument, regardée (c'est la preuve du correctif, pas un gate). Les specs e2e : à la CI, sauf la
  règle WOW23 (« seulement si le jeu complet concerné est plus rapide en local que le job de CI »). La lane de couture
  PARCOURT les écrans de l'arbre assemblé (ce que la CI ne fait pas).
- **I4** — l'instrument ne s'attribue pas le statut 3-bis : dire « c'est la pile locale que la règle 3-bis exige déjà
  pour l'acceptation en direct ; elle suit `ci-avant-docker` (code poussé, en parallèle de la CI, jamais à sa place) ».
- **I5** — enregistrements d'acceptation (`docs/audits/acceptation/<G>/<date>-<sha9>.md`) quand une vague coche des
  tâches d'un groupe d'audit à preuve exécutable : geste de l'orchestrateur, avant la poussée (`check_acceptation.py`).
- **I6** — claims : `--owner`, renouvelées à chaque point de reprise (bail 6 h), posées aussi sur le plan de tout autre
  propriétaire touché, relâchées après le merge.
- **I7** — une décision de Reda prise pendant un run va dans `docs/audits/decisions.yml` ou `docs/claude-memory/`,
  jamais seulement dans le fichier d'état du run.
- **I8** — étage « vraie vie » de L5 : le deploy et l'activation en prod sont des gestes de Reda, listés ; le jeu
  anonymisé seulement si la pile principale est libre, ses captures jamais sur une branche poussée.
- **I9 + faits 5** — L5 dure plusieurs sessions PAR NATURE (jours d'usage réel, fenêtres de quota) : le dire dans la
  ligne de coût, chaque session finit à un merge ; il n'est lancé que nommé par Reda. Fable : seulement les cas (a)(b)(c)
  de `CLAUDE.md` (en L4 : la critique finale SI ≥ ~40 tâches pliées ou surface à haut risque, sinon opus) ; retirer la
  passe Fable « revalidation du harnais ».
- **I10** — gravité : reprendre l'échelle de `docs/audits/METHODE.md` (S1-S4) partout à la place de A / B / C ; donner la
  correspondance une fois.
- **I11** — poste : le tour 0 MESURE (cœurs, mémoire, disque libre, autres piles) et fixe le nombre d'agents à
  navigateur ; rappeler les plafonds écrits en mémoire, la QA de nuit de 23 h, le ménage de 03 h UTC qui supprime les
  worktrees inactifs depuis 7 jours (donc : état poussé, jamais seulement dans un worktree).
- **I12 + rejeu I4** — quota : nommer l'outil (`mcp__ccd_session_mgmt__get_usage`, fenêtre « Weekly · all models »),
  établi dans l'application de bureau seulement ; illisible → tour 0 seul, et la ligne de coût demande le chiffre à
  Reda. Contexte de l'orchestrateur ≥ 70 % → écrire l'état avant de continuer.

## Importants — rejeu
- **I1** — fiche d'invariant : en plus des endroits (grep), une MATRICE champ × condition (ex. frappe : Échap,
  « Terminer », hors ligne, changement d'écran) que la garde parcourt ; la classe est donnée en CIBLE au relecteur du
  tour suivant.
- **I2** — PR brouillon dès le tour 0, et lecture de chaque job de CI CONTRE le périmètre (« ce contrôle lit-il
  vraiment ce module ? » : api-fuzz ne lisait pas Tâches). La lane du changement de contrat possède le serveur ET tous
  ses lecteurs (client d'API, mocks, specs).
- **I3** — coutures : table des identifiants partagés (classe CSS, prop, `data-*`, code HTTP, événement) avec
  propriétaire, tenue par la consolidation, vérifiée par grep des deux côtés par la lane de couture.
- **I5** — sonde de régime : règle TOTALE (tout cas tombe dans une classe ; signaux contradictoires → MIXTE) ; chercher
  dans tout le dépôt (`.claude/`, `scripts/`, `docs/`, pas seulement `apps|features|pages`) par les noms de la demande
  ET leurs synonymes (« widget » → tuile) ; une demande qui vise un outil ou une méthode (pas un produit) se classe par
  la même règle sur l'artefact visé (la skill go-deep existe → EXISTANT / MIXTE, pas NEUF).
- **I6** — événement « demande croisée » ; l'état `reste` cité par `etat.md` doit exister dans le registre.
- **I7** — le rédacteur des tests premiers : son brief (section de `brief-lane.md`, pas un gabarit de plus), son modèle,
  son moment (après la consolidation, avant les lanes, sur la branche d'où elles partent).
- **I8** — outils : les scripts de la session (capture, semis, remise à zéro, lancement) ne sont pas sur `main` et le
  script de mesures DOM n'existe pas. NE PAS ajouter de scripts dans cette PR. Dire la vérité : le premier L4 écrit ses
  scripts d'instrument depuis le gabarit, dans son dossier de travail ; un critère du contrat qui exige un outil
  absent se juge par paires tant que l'outil n'existe pas ; « promouvoir les scripts dans `scripts/` après un premier
  L4 réussi » = une suite, listée dans `conception.md`.
- **I10** — L5 : ajouter ce qui aurait changé quelque chose — le moteur WebKit de Playwright pour les parcours iPhone
  (installé sur ce poste, absent de la config : à vérifier au tour 0, jamais supposé), une SEMAINE SIMULÉE par l'horloge
  pour tout module à rythme (tâches, relances, échéances), la lecture de la prod APRÈS le deploy de Reda (lecture seule,
  accord permanent `prod-read-access`). Rétrograder en « expériences, jamais une décision » : l'estimation de Chapman et
  la revalidation du harnais.
- **I11** — lanes : `plan_lanes.py` quand les corrections sont des tâches de plan avec `Files:` ; sinon la table fichier
  → lane de la consolidation (elle a marché), vérifiée disjointe.
- **Restes du module Tâches** dans les gabarits : étiquetés « exemple (module Tâches, 19-20/11) ».

## Importants — faits
- **1** — surcoût de L5 : « non mesuré » ; retirer « 1,3-1,5 × » et « +25 % ».
- **2** — « 5-65 % » : préciser « évaluateurs HUMAINS d'utilisabilité (Hertzum & Jacobsen 2001) ; non mesuré pour des
  relecteurs LLM ».
- **6** — « ≈ 25 % half-done » : citer les nombres de la rétro tels quels (143 réglées, 37 à moitié, 5 non, 3
  régressions sur 191 contre-vérifications) ; si la somme ne tombe pas, le dire, ne pas arrondir.
- Optionnels à faire (une ligne chacun) : `--owner` ; « 8 lanes + une boucle d'audit » pour 94-99 % de CPU ; « ≥ 44 px »
  retiré ou étiqueté choix de conception ; K4 compare des choses comparables ; réserves ImpossibleBench dans
  `conception.md`.

## Écartés (avec raison)
- Promouvoir tout de suite les scripts d'instrument dans `scripts/` : hors de cette PR (non testés hors Tâches).
- Un gabarit de plus pour le rédacteur de tests : une section suffit.
