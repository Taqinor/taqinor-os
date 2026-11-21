# Brief commun des relecteurs — module Calepinage, tour 1 (go-deep L5)

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## Pour qui tu juges
Reda, fondateur (non-codeur) d'un installateur solaire marocain (résidentiel, tertiaire/industriel, pompage agricole).
Son équipe : des COMMERCIALES qui ne sont pas ingénieures (bureau, parfois tablette ou téléphone en visite) et un
technicien d'études. Sa demande, mot pour mot : « enhance my calpinage module, i want it to have much more
functionalities as the big players of the market have (like pvsys and similar) but i want also to be extremely simple
and easy to use, and the most pretty calpinage module » puis « you went very fast… do a real work… make it really
compete with the named competitors… much more simple and specially much more pretty and easy to use ».
Ton travail n'est PAS de relire du code : c'est d'UTILISER le produit réel comme cet utilisateur, de le REGARDER, et de
dire sans complaisance ce qui n'est pas au niveau des références. Tu n'as pas vu les analyses précédentes : c'est voulu.

## Ce que tu as sous la main
- La fiche de l'instrument : `fiche-instrument.md` (même dossier que ce brief) — LIS-LA EN PREMIER : adresse, ton
  compte, ce qui est absent (carte satellite : fond de repli gris ; pas de worker Celery ; fonctions à clé éteintes).
- Playwright 1.65 (Chromium et WebKit installés). Tes scripts sont des fichiers `.mjs` qui commencent par
  `import { chromium, webkit, devices } from 'file:///C:/dev/taqinor-os/.claude/worktrees/calpinage-module-enhance-04bba5/frontend/node_modules/playwright/index.mjs'`
  (l'import nu `'playwright'` ne résout PAS depuis le scratchpad). Modèle qui marche : `T0/fumee.mjs` (connexion,
  captures, écoute des erreurs console et des réponses ≥ 400). Tu écris tes scripts dans TON dossier `T1/<ton code>/` (chemin dans ton prompt), tu fais de VRAIS
  gestes (clic, frappe, glisser, clavier, molette) et tu REGARDES chaque capture avec l'outil Read. Navigateur
  Chromium sans tête ; pour le téléphone : `devices['iPhone 13']` (WebKit si installé, sinon Chromium en 390 × 844
  tactile — dis lequel).
- Le dépôt en LECTURE seule (`C:/dev/taqinor-os/.claude/worktrees/calpinage-module-enhance-04bba5`) pour comprendre un
  comportement vu à l'écran — jamais pour remplacer l'usage. Hooks utiles : `data-testid="cal-…"`, ids `rp9-…`,
  specs `frontend/e2e/calepinage-*.spec.js` et `frontend/e2e/acceptation/acal*.spec.js` (elles montrent comment
  tracer un toit et poser des panneaux par script — inspire-toi de leurs gestes).
- L'état des lieux du tour 0 : `docs/audits/2026-11-20-calepinage-l5.md` (§ 3 diagnostic, § 5 contrat de sortie K1-K15)
  — ne redécouvre pas le connu ; tu peux juger qu'un point « connu » est pire qu'écrit.
- Le plancher d'oracles : `.claude/skills/qa-explorer/SKILL.md` STEP 2 (oracles 1-10) et STEP 3 (règles 1-12) : tout
  4xx/5xx inattendu, toute erreur console, toute liste vide après une création est un constat.

## Règles
1. Tu n'édites AUCUN fichier du produit ni du dépôt. Tes seules écritures : tes scripts, tes captures, ton fichier de
   constats `registre/constats/T1-<ton code>.jsonl` et ton rapport `T1/<ton code>.md` (chemins absolus dans ton prompt).
2. N'arrête ni ne relance l'instrument ; AUCUNE commande `docker` ; jamais la prod ni un autre hôte que
   `http://127.0.0.1:5231`. Si l'instrument ne répond plus : dis-le et arrête-toi.
3. Chaque constat est PROUVÉ : gestes exacts + capture regardée + ce que tu attendais. Ce que tu n'as pas vu de tes
   yeux va dans « à vérifier », pas au registre.
4. Calibrage : un constat = ce que l'utilisateur remarquerait, ou qui le ferait hésiter, chercher, se tromper, perdre
   du temps, ou trouver l'outil moins beau ou moins sérieux que les références. Pas de préférence sans raison, pas de
   durcissement hypothétique. Un défaut dû à l'instrument (carte grise, pas de worker, clé absente) n'est PAS un
   constat : note-le dans « non essayé ». Chaque constat cite le critère `K<n>` du contrat (§ 5 du dossier) qu'il
   touche, sinon `hors-contrat`.
5. Gravité : S1 chiffre faux / perte de données · S2 geste courant cassé ou impossible, ou défaut qui saute aux yeux
   dès la première heure · S3 gêne ou laideur au quotidien · S4 finition.
6. Beauté : juge PAR PAIRES (nous / référence, sur les images du dossier `references/` quand elles existent) et par
   MESURES (tailles de texte distinctes, cibles < 44 px, alignements, densité, contraste) — jamais une note seule.
7. Écris au fil de l'eau : une ligne JSON dès qu'un constat est prouvé ; seul ce qui est sur disque survit.
8. Dis aussi ce qui est BIEN (à ne pas casser) et ce que tu n'as PAS pu essayer.
9. En plus des défauts, PROPOSE : pour ton axe, les 5 à 10 changements qui rapprocheraient le plus le module des
   références (chaque proposition = le geste ou l'écran visé, l'effet attendu, la référence qui le fait).

## Format d'un constat (une ligne JSON par constat, jamais modifiée après écriture)
`{"id":"T1-<code>-001","tour":1,"relecteur":"<code>","axe":"F|S|Be|A11y|D","vue":"bureau-clair|bureau-sombre|tablette|iphone-clair|iphone-sombre|serveur","gravite":"S1|S2|S3|S4","ecran":"…","gestes":"…","capture":"<chemin absolu>","attendu":"…","critere":"K<n>|hors-contrat","classe":null,"avant_merge":null}`

## Forme du rapport (français simple) — `T1/<ton code>.md`
1. Verdict en trois lignes. 2. Constats : renvoi aux ids du registre + une ligne chacun, triés par gravité.
3. Tes propositions (règle 9). 4. Ce qui est bien. 5. Non essayé, et pourquoi.
Message final : verdict + nombre de constats par gravité + les S1-S2, 15 lignes au plus.
