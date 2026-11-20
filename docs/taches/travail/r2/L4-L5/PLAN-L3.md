# L3 — concevoir les niveaux L4 et L5 de la skill `go-deep` (plan de l'orchestrateur)

Demande de Reda (20/11/2026), mot pour mot : « lets learn from what we did here and make it an L4 or l5, but before doing
it keep in memory all what we did, and search extremely well on how people do and what are the best ways of going
forward, and maybe you can build an L4 and L5, where what we just did can be just l4 and l5 is much more powerfull. and
i want it to automaticly detect if we build a new thing or enhance what exists and adapt based on that. go L3 on this ».

Contraintes au départ : quota hebdomadaire à 80 % (réinitialisation dans 5 j 18 h) → équipes MAIGRES ; contexte de
l'orchestrateur à 90 % → tout s'écrit sur disque ; règle toujours en vigueur dans cette session : pas de question à
Reda (décider, noter le choix).

## Ce qui est fait
- [x] Mémoire : `../RETRO-METHODE.md` (tout ce qu'on a fait, chiffres, ce qui a marché, ce qui a coûté, idées).
- [ ] Pointeur dans la mémoire partagée (`C:\Users\kasri\.claude\projects\C--dev-taqinor-os\memory\`) : à faire au
      rendu final (une ligne d'index + la session du 17/11).

## R1 — COMPRENDRE (recherche ; un rapport par lane dans `recherche/<nom>.md`, 150 lignes au plus, sources citées)
Budget : 20 recherches web par lane au plus (plafond partagé de 200 par tour) ; WebFetch direct sur les sources ;
sonnet, effort high ; bloc d'ancrage dans chaque prompt.
- `A-anthropic` : ce qu'Anthropic publie sur les systèmes multi-agents, les harnais pour agents longs, la vérification
  par contexte neuf, l'évaluateur-optimiseur, les workflows et sous-agents de Claude Code, les skills.
- `B-agents-de-code` : comment les équipes font tourner des agents de code de bout en bout (spec-driven : Spec Kit, Kiro,
  BMAD ; boucles « Ralph » ; compound engineering ; Superpowers ; Devin / Cursor / Codex : agents d'arrière-plan,
  revues ; ce qui marche et ce qui échoue, chiffres à l'appui).
- `C-qualite-logiciel` : la pratique humaine qu'on a réinventée — tests exploratoires par sessions, bug bash, dogfooding,
  évaluation heuristique et parcours cognitif, tours d'utilisabilité, QA de design, critères de sortie, courbes de
  découverte de défauts et estimation de ce qui reste (capture-recapture), tests de mutation, « definition of done ».
- `D-neuf-ou-existant` : construire du neuf contre améliorer l'existant — ce qui change dans la méthode (tests de
  caractérisation, analyse d'impact, filets de régression, « strangler », inventaire) et comment le DÉTECTER
  automatiquement (signaux du dépôt, de la demande, de la prod) ; ce que font BMAD brownfield, Spec Kit, Kiro.
- `E-fiabilite-llm` : ce que la recherche dit de la vérification par LLM (complaisance, débat multi-agents, juges,
  auto-cohérence, triche sur les tests, ancrage), du coût (multi-agent ≈ 15×) et de la tenue des longues tâches
  (fichiers d'état, points de reprise, gestion du contexte).
- `F-maison` : lecture seule du dépôt — la skill actuelle (`.claude/skills/go-deep/SKILL.md`), son crochet de détection
  (`.claude/settings.json`), `CLAUDE.md` (règles de flotte, modèles, WOW23), `docs/audits/METHODE.md` (méthode d'audit
  v3, acceptation), les skills `qa-explorer`, `error-autopilot`, `audit`, `docs/claude-memory/lecons-construction-qjr5.md`
  et `../RETRO-METHODE.md` : ce que L4 / L5 doivent RÉUTILISER, ne pas dupliquer, et où ils se branchent.

## R2 — CREUSER (un concepteur opus) → `projet-skill.md`
À partir des six rapports et de la rétro : le texte COMPLET de la skill révisée (L1-L3 inchangés dans leur esprit +
L4 + L5 + la détection neuf / existant + les garde-fous de coût), le crochet de détection des phrases (« go L4 »,
« go L5 », et leurs formes en mots), et un tableau « ce que la session du 19-20/11 aurait fait différemment ».
Idée directrice à éprouver : L4 = la boucle prouvée ici (tours de relecteurs neufs sur le RÉEL → consolidation →
lanes → couture → CI → tour suivant, jusqu'au seuil de sortie) ; L5 = L4 + ce qui manquait (registre machine des
constats, critères de sortie chiffrés au tour 0, classes de défauts transformées en gardes permanentes, parcours des
relecteurs devenus suite d'acceptation, estimation de ce qui reste, étage « vraie vie », reprise multi-sessions).

## R3 — VALIDER (trois vérificateurs NEUFS, lentilles différentes) → `validation/<lentille>.md`
- `rejeu` : rejouer la session du 19-20/11 contre le projet : chaque défaut de la rétro § 6 est-il empêché ? chaque
  réussite § 5 est-elle gardée ? coût estimé contre coût mesuré.
- `maison` : cohérence avec `CLAUDE.md` (aucune règle contredite, pas de double emploi avec audit / qa-explorer /
  acceptation), faisabilité sur ce poste (4 cœurs, 34 Go, quota), sécurité (jamais la prod, jamais de deploy).
- `faits` : chaque affirmation tirée de la recherche a-t-elle sa source ? rien d'inventé.
Boucler R2 ↔ R3 jusqu'à ce qu'un tour n'apporte rien.

## R4 — REVUE FINALE
Un critique de complétude (un passage Fable permis par la règle de la maison : décision qui façonne beaucoup de travail
futur) → puis écrire `.claude/skills/go-deep/SKILL.md` + le crochet dans `.claude/settings.json` sur une branche
`claude/go-deep-l4-l5`, PR docs / config seule, CI rapide, merge par la file ; mémoire partagée
(`docs/claude-memory/`) ; rapport à Reda en langage simple (ce que sont L4 et L5, quand les employer, ce qu'ils
coûtent, ce qui n'est pas couvert).

## Journal
- 20/11 : rétro et plan écrits ; brief commun `brief-recherche.md` ; R1 LANCÉ : six lanes sonnet (A-anthropic,
  B-agents-de-code, C-qualite-logiciel, D-neuf-ou-existant, E-fiabilite-llm, F-maison), rapports attendus dans
  `recherche/`. À leur retour : lire les messages finaux (15 lignes chacun), PAS les rapports entiers ; lancer R2 (un
  concepteur opus qui lit les six rapports + la rétro et écrit `projet-skill.md`) ; puis R3 (trois vérificateurs neufs),
  R4 (critique + PR `claude/go-deep-l4-l5` : `.claude/skills/go-deep/SKILL.md` + crochet de `.claude/settings.json`).
- Quota hebdomadaire au lancement : 80 %. Contexte de l'orchestrateur : 90 % (une compaction est probable : tout ce
  qu'il faut pour reprendre est dans ce fichier, dans `../RETRO-METHODE.md` et dans `../ETAT.md`).

