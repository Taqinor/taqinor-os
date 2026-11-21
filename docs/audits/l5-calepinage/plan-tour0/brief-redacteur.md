# Brief commun des rédacteurs — complément ACAL « L5 » du 2026-11-20 (tâches v3)

Dépôt : `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5` (lecture seule : tu n'édites AUCUN
fichier du dépôt ; tu n'exécutes ni docker ni tests ; `python`/`git grep`/Read/Grep/Glob seulement).
Ta sortie : UN fichier de lot dans le scratchpad (chemin donné dans ton prompt) + un compte rendu ≤ 30 lignes.

## Contexte
Reda (fondateur, non-codeur) : « enhance my calpinage module… much more functionalities as the big players (PVsyst and
similar)… extremely simple and easy to use, and the most pretty calpinage module… only add tasks to the plan ».
Le module existe déjà (≈ 580 tâches CAL/CALX + 358 ACAL construites). Les tâches que tu écris seront construites plus
tard par des agents qui n'auront QUE le texte de la tâche : elle doit être exacte, bornée, vérifiable.

Rapports d'inventaire et de recherche à LIRE avant d'écrire (scratchpad `r1/`, même dossier parent que ce brief) :
- `r1/a1-backend.md` (capacités serveur A/B/C/D), `r1/a2-frontend-erp.md` (écrans ERP, 36 onglets, parcours),
  `r1/a3-atelier-3d.md` (constructeur 3D roofPro11), `r1/a4-plans-mecanique.md` (décisions D-ACAL/D-CALX, règles des
  gardes, gabarits verbatim B et D en Partie 3), `r1/c1-simulation-tools.md` (PVsyst & co, sources),
  `r1/c2-sales-design-ux.md` (Aurora, OpenSolar, Reonic…, sources).
Lis seulement les sections utiles à ton lot. Méthode : `docs/audits/METHODE.md` §A.4 (critères C1-C13) et §C.2 (forme v3).

## Étape 1 — VÉRIFIER la prémisse de chaque tâche du squelette (obligatoire, avant d'écrire)
Pour chaque tâche de ton lot : ouvre le code réel et prouve (a) que le manque existe AUJOURD'HUI (sinon : NE PAS écrire
la tâche — la lister « déjà présent : `fichier::symbole` » dans ton compte rendu), (b) qu'aucune tâche ouverte/GATED ne
la couvre déjà (`git grep -n "<mot>" -- docs/plans docs/PLAN2.md docs/ERROR_PLAN.md`), (c) qu'elle ne contredit aucune
décision (liste ci-dessous). Si la prémisse est partiellement fausse : réécris le titre sur le VRAI manque. Tu peux
SCINDER une tâche qui porte deux comportements (utilise un id libre de ta plage) ou en SUPPRIMER une. N'invente pas de
tâche hors squelette, sauf un manque prouvé de la même surface (2 au plus, ids de ta plage).

## Étape 2 — Écrire chaque tâche au format v3 (UNE ligne physique, sans retour à la ligne)
`- [ ] ACALnnn — **<Verbe + objet ; fini quand <fin bornée observable>>** : Constat : C-ACAL-L5-nnn (C<n>, S<n>, STATIQUE (lecture du 20/11 sur e9b08b57e)) — <mécanisme / manque> à `fichier::symbole` ; référence : <produit concurrent + ce qu'il fait, d'après r1/c1 ou r1/c2> ; Priorité : P<1-3>. Given … When … Then …. Persistance : …. Emplacement : `fichier::symbole` (N l.). Code net : … ; lignes nettes ≤ N. Appelants : …. Assertions existantes : …. Jumeaux : …. Listes figées : …. Contrat partagé : …. Test rouge d'abord : …. Preuve en direct : …. Hors périmètre : …. (gen manuel e9b08b5) Files: `chemin1`, `chemin2` (ROUTINE|SCHEMA|ARCH) (@after: ACALxxx) (@lane: calepinage/<surface>) (@model: sonnet|opus|haiku)`

Règles de forme (gardes bloquantes — `r1/a4-plans-mecanique.md` Partie 2 les détaille) :
1. Les 14 libellés exacts, dans cet ordre : `Constat :`, `Given … When … Then`, `Persistance :`, `Emplacement :`,
   `Code net :`, `Appelants :`, `Assertions existantes :`, `Jumeaux :`, `Listes figées :`, `Contrat partagé :`,
   `Test rouge d'abord :`, `Preuve en direct :`, `Hors périmètre :`, `(gen manuel e9b08b5)` puis `Files:` en DERNIER.
2. Jamais de `n/a` nu : toujours `n/a — raison`. Jamais « Si (a)/(b) ». UN comportement par tâche.
3. Ancres : `fichier::symbole` entre backticks, le symbole DOIT exister dans le fichier aujourd'hui (vérifie par grep).
   Un fichier que la tâche CRÉE se cite SANS `::` (chemin seul). Jamais `fichier:ligne`.
4. `Appelants`, `Assertions existantes`, `Jumeaux`, `Listes figées` = le RÉSULTAT de greps que tu as exécutés
   (ex. « `PanneauProduction.jsx::lancer` ← 1 écran (onglet production) ; grep `simuler(` dans `frontend/src` : 3 »),
   jamais « à chercher ». `Assertions existantes` nomme les tests/goldens/specs e2e/contract_samples qui exercent le
   symbole → « restent verts » ou « à réaligner » (alors le fichier figure dans `Files:`).
5. `Test rouge d'abord` : dans un module de test EXISTANT (`chemin::Classe::test` ou `chemin (nouveau cas « … »)`), avec
   un MUTANT (« ligne changée ⇒ échec ») ; un fichier de test neuf seulement avec « Nouveau fichier car : <raison> » et
   jamais un nom de fichier portant l'id de la tâche. Spec Playwright neuve : `frontend/e2e/calepinage-<sujet>.spec.js`.
6. Un écran/panneau NEUF sous `frontend/src/features/calepinage/` : `Files:` nomme le fichier de montage
   (`frontend/src/features/calepinage/atelier/onglets.js` ou `frontend/src/features/calepinage/module.config.jsx`) ET le
   texte dit « onglet monté dans … » ou « route déclarée + entrée de nav ».
7. Une tâche qui touche backend ET frontend : la clause `Contrat partagé :` nomme l'échantillon
   `backend/django_core/apps/calepinage/contract_samples/<x>.json` (affirmé par le test backend ET importé par le test
   frontend). Si le contrat est une tâche M0 du squelette : `(@after: ACAL<M0>)`.
8. PROPRIÉTÉ : chaque chemin de `Files:` doit appartenir au propriétaire `calepinage` (voir la liste des globs dans
   `r1/a4-plans-mecanique.md` §2.4). En particulier un fichier NEUF dans `apps/web/src/lib/` n'est couvert que s'il
   commence par `roof`, `shadingEngine`, `horizonEngine`, `productionEngine`, `obstacles`, `freeLayout`,
   `panelSelection`, `estimatorBrainV` ; préfère `apps/web/src/scripts/roofPro11/<nouveau>.ts`. Un fichier d'un autre
   propriétaire (crm, ventes, stock, web, deploy, `frontend/playwright.config.js`, `scripts/`) ⇒ NE PAS l'inclure :
   reformule la tâche pour rester dans le périmètre, ou classe-la « à router ailleurs » dans ton compte rendu.
9. Fichiers mono-écrivain (une seule lane à la fois — mets la même `@lane` aux tâches qui les touchent) :
   `apps/web/src/scripts/roof-tool-pro11.ts`, `apps/web/src/scripts/roofPro11/prefill.ts`,
   `frontend/src/pages/ventes/ToitureDesign.jsx`, `backend/django_core/apps/calepinage/services/layout.py`,
   `backend/django_core/apps/calepinage/models.py` + migrations. Surfaces en AJOUT seulement : `atelier/onglets.js`,
   `frontend/src/api/calepinageApi.js`, `apps/calepinage/views/rattachements.py`, `services/parametres_cles.py`.
10. Un fichier ≥ 2 000 lignes ne grossit pas : la tâche crée un fichier voisin et n'ajoute qu'un point d'appel
    (« lignes nettes ≤ N » dans le gros fichier).
11. `@model` : `opus` pour `core/**`, moteur de devis, droits, argent ; `sonnet` par défaut ; `haiku` pour le mécanique.
    `@lane` suggérées : `calepinage/atelier-web` (apps/web roofPro11), `calepinage/atelier-erp` (ToitureDesign,
    BuilderDom, rail), `calepinage/resultats` (production, pertes, graphiques), `calepinage/simulation` (services de
    simulation, étapes), `calepinage/site` (météo, horizon, terrain), `calepinage/style`, `calepinage/gardes`.
12. Cible ≤ 2 800 caractères par tâche. Français, phrases courtes, pas de jargon inutile dans le titre.

## Décisions qui CONTRAIGNENT (ne jamais écrire une tâche qui les contredit)
- Le calepinage est l'unique conception d'un devis ; la production que voit un CLIENT est celle du moteur de devis
  (D-ACAL-1/6) ; la simulation du calepinage est l'étude technique interne. Aucune tâche ne change un PDF client
  (`/proposal`, règle #4) ni un statut de devis.
- Zéro chiffre inventé : toute valeur est réelle, dérivée-traçable (source + référence) ou OMISE et nommée (D-ACAL-7,
  D-CALX 7). Une tâche ne fixe JAMAIS un pourcentage/coefficient « par défaut » en dur dans le code.
- L'argent ne vit que dans `apps/ventes` (le calepinage ne calcule ni prix, ni LCOE, ni VAN) ; un graphique financier
  ne fait qu'AFFICHER des données déjà servies.
- Aucune dépendance ni donnée payante (D-CALX-PAYANT) : Google Solar, Meteonorm, Solcast, LiDAR payant, Nearmap = non.
  pvlib est adopté (épinglé 0.16.1). Trackers : hors périmètre. Pas sous-horaire (CALX200 GATED). Import .PAN/.OND :
  déjà CALX339/356/357 (bloquées sur des fichiers de Reda) — ne pas dupliquer.
- Charges vent/neige de structure : saisie société sourcée (décision 7 du 21/09) — pas de calcul normatif.
- « Brancher plutôt que retirer » toute fonction serveur à moitié construite (D-ACAL-17..20).
- Un seul calepinage OUVERT par lead ; variantes = options ; approbation jamais par l'auteur ; atelier en français.
- Lecture d'une autre app : seulement par ses `selectors.py`/`services.py` (jamais ses modèles).
- Multi-société : toute donnée filtrée par `request.user.company`.
- Raccourcis jamais destructifs ; une erreur désigne le champ fautif ; aucun prénom en dur.

## Étape 3 — VALIDER ton lot toi-même (obligatoire)
`PYTHONIOENCODING=utf-8 python "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/valide_lot.py" "<ton fichier de lot>"`
→ corrige jusqu'à « 0 en echec » (clauses, ancres, propriétaire de chaque fichier, @model, catégorie).

## Compte rendu (≤ 30 lignes)
Tâches écrites (ids), tâches du squelette SUPPRIMÉES avec la preuve « déjà présent » (`fichier::symbole`), tâches
réécrites et pourquoi, tâches « à router ailleurs » (autre propriétaire), sortie de la dernière ligne du validateur,
et tout fait du squelette que tu as trouvé FAUX.

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
