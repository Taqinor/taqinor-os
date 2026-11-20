# Niveaux L4 et L5 de `go-deep` (20/11/2026)

**Demande de Reda (20/11/2026)** : tirer la leçon des tours de revue du module Tâches (19-20/11, PR #1481) et en faire
un niveau L4 (ce qui a été fait, rendu reproductible) et un niveau L5 « much more powerful », qui détectent seuls si
l'on construit du neuf ou si l'on améliore l'existant.

## Ce qui existe maintenant
- `.claude/skills/go-deep/SKILL.md` : cinq niveaux. L1-L3 inchangés (comprendre). **L4 « ship-grade »** (« go L4 »,
  « go ship-grade », « lance un L4 ») : des tours de relecteurs neufs qui UTILISENT le produit réel sur une pile privée,
  corrections par lanes, contre-vérification par des relecteurs neufs, jusqu'à un contrat de sortie chiffré écrit au
  tour 0. **L5 « all the way »** (« go L5 », « go all the way ») : L4 + figer ce qui marche avant d'y toucher, une garde
  par classe de défaut prouvée rouge sur le défaut d'origine, parcours iPhone sous WebKit, semaine simulée, étage
  « vraie vie » avec Reda sur son appareil, lecture de la prod après son deploy. Procédures : `L4.md`, `L5.md` ;
  gabarits : `gabarits/` ; sources et statut de chaque choix : `conception.md` (même dossier).
- **Régime** détecté avant tout niveau, lu sur `origin/main` : NEUF / EXISTANT / MIXTE, par la part des promesses de la
  demande déjà servies ; annoncé en une ligne ; Reda peut l'imposer d'un mot.
- Le crochet de `.claude/settings.json` reconnaît « go L1 » … « go L5 » ; une phrase qui cite plusieurs niveaux, une
  négation ou une question ne lance jamais L4 / L5.

## Règles durables
- **L4 et L5 ne sont jamais choisis automatiquement** : seulement quand Reda les nomme. Le choix automatique s'arrête
  à L3 et PROPOSE L4 en une ligne, avec le nombre de tours que le quota permet.
- **Coût** : mesuré UNE fois (19-20/11) — tour 0 + 3 tours + finale ≈ 74 points du quota hebdomadaire, dont une part
  d'une autre session. L5 : non mesuré, plusieurs sessions par nature. Tous les seuils de `L4.md` marqués « (start) »
  sont des valeurs de départ : à recaler après le premier L4 lancé depuis la skill.
- **Pile de revue (« instrument »)** : jamais le vrai `.env`. La session du 19/11 l'avait passé à son conteneur
  (clés d'IA réelles chargées, port ouvert sur toutes les interfaces du poste ; pile arrêtée le 20/11 ; personne n'a
  vérifié si ces clés ont servi pendant la revue) :
  le gabarit impose désormais un lanceur à variables forcées et un contrôle de tour 0 qui arrête tout sinon.
- La vérification finale (un relecteur neuf sur l'écran réel + une critique du diff serveur) est toujours jouée avant
  le dernier merge, même quand le quota coupe les tours.
- Rien de tout cela ne déploie : Claude s'arrête au merge.

## Pas encore fait
- Aucun L4 ni L5 n'a été lancé DEPUIS la skill : le premier calibrera les valeurs de départ.
- Les scripts de l'instrument (lancement, semis, captures, mesures) ne sont pas dans `scripts/` : le premier L4 les
  écrit depuis le gabarit ; les promouvoir ensuite est une suite listée dans `conception.md`.
- Notes de conception complètes (rétro, six rapports de recherche, trois vérifications, tri) : branche
  `claude/erp-task-manager-ai-f8db1b`, dossier `docs/taches/travail/r2/` (`RETRO-METHODE.md`, `L4-L5/`).
