# Brief — réassemblage de la vague 2 corrigée dans les plans (campagne L5 calepinage, 21/11/2026)

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## La situation
La vague 2 des tâches de plan du module Calepinage (TAQINOR OS) a été écrite (472 tâches), intégrée une première fois
dans une PR docs-only (#1517, branche `claude/calepinage-vague2`, worktree
`C:\dev\taqinor-os\.claude\worktrees\l5-vague2-integ`), puis ENTIÈREMENT revérifiée contre le code et corrigée en
trois passes. Le texte corrigé vit dans des copies d'édition hors dépôt. Ton travail : remettre ce texte corrigé dans
les fichiers de plan de la branche, régénérer le dossier, faire passer toutes les gardes, pousser. Tu ne merges PAS.
Livraison : docs seulement, rien n'est construit.

## Sources (dossier `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\`)
- `l5\corr\src-*.md` : 19 copies d'édition (17 lots, `D8-FABLE`, `MANQUES`). Format : bloc `## ACALnnn @@ <fichier de
  plan>` puis la tâche, une clause par ligne. Un bloc dont le corps commence par `SUPPRIMÉE` est une tâche retirée
  (garde sa raison pour le dossier). NE MODIFIE PAS ces fichiers, sauf erreur de forme qu'une garde te force à
  corriger — alors corrige dans la copie d'édition ET dis-le.
- `corr_outils.py` (même dossier racine) : `lire_edition(chemin)` rend `(id, maison, ligne recollée | None, raison)` —
  réutilise-le pour recoller chaque tâche en UNE ligne.
- `l5\corr\rangement-nouvelles.md` : pour chaque tâche créée pendant les corrections (id ≥ ACAL1033), sa section
  (M1 / M2 / GATED), son domaine (D1…D8) et la tâche après laquelle la ranger.
- `coherence_vague.py` (racine du scratchpad) : contrôle de cohérence de la vague (voir son en-tête d'appel dans
  `l5\corr\BRIEF-passe3.md`) ; il doit rendre « CYCLES : 0 » et aucune autre rubrique que les neuf `selectors.py`.
- Les scripts du premier intégrateur, à réemployer et adapter : dans le worktree
  `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5\docs\audits\l5-calepinage\lots2\integ\`
  (`assemble.py`, `inserer.py`, `dossier.py`, `reconcile.py`). Ce worktree-là (branche de notes) : lecture seule pour toi.
- La critique finale et les rapports : `l5\verif2\CRITIQUE-fable-vague2.md`, `l5\verif2\rapport-*.md`.

## Où écrire : UNIQUEMENT le worktree `C:\dev\taqinor-os\.claude\worktrees\l5-vague2-integ` (branche `claude/calepinage-vague2`)
Commence par `git fetch origin main` puis `git merge FETCH_HEAD` (jamais de rebase ni de force-push ; un conflit se
résout en gardant les deux côtés). Les baux des douze fichiers de plan sont tenus par
`Reda_Laptop/claude/calepinage-vague2` : renouvelle-les (`python scripts/plan_claims.py renew <clé>… --owner
"Reda_Laptop/claude/calepinage-vague2"`) au début et avant de pousser ; ne les libère pas.

1. **`docs/plans/PLAN_AUDIT_CALEPINAGE.md`** — le bloc de la vague 2 s'insère maintenant DIRECTEMENT dans ce fichier,
   juste avant `## DONE LOG` (même mécanique que `inserer.py` : fins de ligne et BOM du fichier respectés). Structure
   du bloc : celle de `docs/audits/l5-calepinage/INSERTION-PLAN_AUDIT_CALEPINAGE.md` de la branche (titre
   `## Groupe ACAL — complément du 2026-11-21 (vague 2) · format v3`, sections `### ACAL — M1 bloquant-fondateur`,
   `### ACAL — M2`, `### ACAL — GATED (ne PAS auto-construire)`, `### ACAL — Acceptation en direct…`, sous-titres
   `#### D<n> — …`), avec les tâches dont la « maison » est ce plan (ou le fichier INSERTION), dans l'ordre d'origine
   du fichier INSERTION, les tâches supprimées retirées, les tâches neuves rangées selon `rangement-nouvelles.md`,
   et toute tâche dont le titre commence par `[GATED` dans la section GATED. Puis SUPPRIME le fichier
   `docs/audits/l5-calepinage/INSERTION-PLAN_AUDIT_CALEPINAGE.md` de la branche (il ferait doublon).
   En-tête du groupe : réécris les paragraphes `>` pour qu'ils soient VRAIS après corrections (voir « En-tête » plus bas).
2. **Les autres plans** (`docs/WEB_PLAN.md`, `docs/plans/PLAN_AUDIT_{CHANTIERS,DEPLOY,DEVIS,LEAD,MOTEUR,PARAMETRES,
   SAV,STOCK}.md`) : chaque ligne de tâche de la vague 2 déjà présente est REMPLACÉE par son texte corrigé, ou retirée
   si elle est supprimée ; les tâches neuves de ce plan sont ajoutées dans le même groupe (section GATED pour une
   tâche `[GATED`). Mets à jour la phrase d'en-tête du groupe si son décompte ou ses renvois sont devenus faux.
   **Deux plans reçoivent un groupe neuf**, sur le patron des autres : `docs/plans/PLAN_AUDIT_SECURITE.md` (ACAL1050)
   et `docs/plans/PLAN_AUDIT_TRANSVERSE.md` (les tâches `(@atomique: …)` : relis la règle de ce plan dans son en-tête
   et dans `docs/audits/METHODE.md` § C.5 avant d'écrire ; une tâche atomique GATED va dans une section GATED).
3. **Deux retouches à des lignes existantes du plan calepinage** (décisions prises, à dire dans le DONE LOG du fichier
   par une ligne datée du 2026-11-21) :
   - la phrase INTERDIT de tête « imprimer le P50 du calepinage sur le devis, le PDF ou la page publique » reçoit la
     précision « (sauf devis de niveau de règles ≥ 15 à calepinage simulé complet — D-ACAL-36, ACAL996 à ACAL1001) » ;
     de même la mention « déclarer `urls.py`, `selectors.py`… » reçoit « (sauf les neuf tâches de la vague 0 du
     complément du 21/11, qui modifient une fonction existante de `selectors.py` et se construisent d'abord) » ;
   - **ACAL487** (GATED « autre propriétaire… », groupe du 20/11) : la décision D-ACAL-38 a répondu et la moitié
     « site public » existe (ACAL1026, `docs/WEB_PLAN.md`, qui porte `@after: ACAL487`). Lis la tâche et ses
     `Files:` : si tous ses fichiers sont au propriétaire calepinage (`python scripts/check_ownership.py --owner-of`),
     retire son tag GATED et sors-la de la section GATED (elle rejoint la section M2 de la vague 2, texte inchangé à
     part le tag et une mention « D-ACAL-38 du 21/11 ») ; sinon laisse-la, et dis dans ton compte rendu ce qui manque
     pour la débloquer (ACAL1026 reste alors bloquée derrière elle : dis-le aussi dans le dossier).
4. **`docs/audits/decisions.yml`** : les listes `taches:` de D-ACAL-36 à D-ACAL-43 = les tâches VIVANTES qui citent la
   décision dans leur clause Constat ou leur tag GATED. Rien d'autre ne change dans ce fichier.
5. **`docs/audits/2026-11-21-calepinage-l5-vague2.md`** (dossier) : régénère la table des constats depuis les plans
   (adapte `dossier.py`), les comptes (par domaine, section, plan, priorité), la liste des tâches retirées (les
   blocs `SUPPRIMÉE` et leur raison, plus celles de la première réconciliation déjà listées), la réserve (ajoute la
   ligne laissée par le lot MANQUES sur la seconde moitié de CAP-D3-17 : « `core/electrique/schema.py` ne dessine le
   limiteur que sur le chemin C&I moyenne tension ; un champ `micro_seul` n'a pas de fiche onduleur… : reprendre
   après ACAL1187 »), et ajoute une section **« Vérification du 21/11 »** qui dit, chiffres comptés par toi dans les
   rapports : 17 vérificateurs neufs (un par lot) ont relu chaque tâche contre le code de `main` ; verdicts par lot
   (OK / à corriger / doublon / déjà construit / à scinder — relève-les dans les `rapport-*.md`) ; deux passes de
   correction par lot puis une passe de cohérence ; les deux relectures adverses au modèle le plus fort (l'architecture
   du moteur partagé, puis la vague entière : 8 bloquants, dont la chaîne D-ACAL-36 réécrite) ; ce que ces passes ont
   changé (tâches supprimées, créées, scindées) ; et les LIMITES telles quelles : aucun test exécuté (tout « rouge
   d'abord » est attendu, non observé), les extractions proposées pour les fichiers de 2 000 lignes sont des lectures
   à confirmer à la construction, le nombre de calepinages touchés par ACAL921 est inconnu tant qu'ACAL1194 n'a pas
   tourné, le document agricole n'imprime pas de production (rien ajouté), le constat T1-T1-013 a maintenant sa tâche
   (ACAL1185). Retire toute phrase devenue fausse (dont « dépendances vers un autre plan écrites en phrase » et les
   renvois au fichier INSERTION).
6. **`docs/claude-memory/calepinage-decisions-fondateur.md`** : vérifie que la ligne du 21/11 dit bien D-ACAL-36 à 43 ;
   ajoute en une phrase les trois faits trouvés par la vérification (surfaces au sol / ombrières / façades lues à 90°
   près aujourd'hui → ACAL921 attend la liste d'ACAL1194 ; la production imprimée d'un devis C&I vient du toit
   déclaré du lead → ACAL1195 ; le format « une page » imprime encore des économies estimées sans consommation
   connue → ACAL1033). Pas d'autre fichier de mémoire.

## En-tête du groupe (plan calepinage) — ce qu'il doit dire, en français clair, sans rien d'invérifié
Décompte réel (tâches du fichier / chez les autres propriétaires, par toi). « Rien n'est construit. » Lecture du code
sur `684d77f02`, chaque tâche relue par un vérificateur neuf le 21/11. Les décisions D-ACAL-36 à 43 (garde le
paragraphe existant, en retirant « ligne laissée telle quelle » puisque la ligne INTERDIT est maintenant précisée).
Les choix pris seul (garde). L'architecture (garde, en ajoutant : la chaîne D-ACAL-36 est ACAL996 → 997 ; 998 ; 1169 →
999 → 1170 → 973 ; 1000 ; 1195 (C&I) ; 1033 (« une page ») ; 1196 ; 1171 ; activation ACAL1001, GATED, après lecture de
la liste des écarts par Reda — reprends les `@after` réels d'ACAL1001). **Ordre de construction** : (0) « vague 0 » —
les neuf tâches qui modifient une fonction existante de `apps/calepinage/selectors.py` (572, 595, 770, 883, 895, 948,
961, 964, 978) et leurs prérequis se construisent D'ABORD, en les nommant au planificateur
(`python scripts/plan_lanes.py … --only <ids>`), parce que la porte « écran ↔ serveur » retient tout écran du
calepinage tant qu'une d'elles est ouverte — vérifie la syntaxe exacte de `--only` dans `scripts/plan_lanes.py` et
donne la liste complète (les neuf + leurs `@after` transitifs encore ouverts) ; (1) contrats seuls sur main d'abord ;
(2) M1 ; (3) M2 ; (4) l'acceptation ACAL1031 par l'orchestrateur. **Dépendances vers un autre plan** : ce sont de vrais
`@after`, que le planificateur respecte. **Simplicité** : chaque tâche d'écran dit son étape, son niveau et son effet
sur le premier écran ; une capacité nouvelle va au niveau expert ; les tâches ACAL869 et ACAL1189 à 1193 réduisent le
niveau essentiel de chaque étape au contenu de sa maquette. **Trois gestes du fondateur attendus** (pas des questions) :
lire la liste d'ACAL1000 avant l'activation ACAL1001 ; lire la liste d'ACAL1194 avant ACAL921 ; créer et tarifer
l'article « kit de fixation » (ACAL1172 le sème sans prix). Garde les paragraphes Écran, Fichiers mono-écrivain et
Hors complément en les corrigeant s'ils sont devenus faux.

## Gardes — toutes vertes avant de pousser (depuis le worktree, `PYTHONIOENCODING=utf-8`)
`check_taches_cablage.py`, `check_ancres_taches.py`, `check_ownership.py`, `check_decisions.py`,
`check_plan_taches_mixtes.py`, `check_build_order.py`, `check_audit_dossier.py` (long : plusieurs minutes),
`check_stages.py`, `audit_registre.py --check`, `codemap_fingerprint.py --check`, et les modules de test de scripts
que le premier intégrateur lançait (voir `gardes3.txt` dans son dossier). `plan_lanes.py` sur CHAQUE plan touché :
compare le nombre de « REFUSÉ » à celui du même plan sur `origin/main` et explique tout écart (attendu : les écrans
du calepinage retenus tant que la vague 0 est ouverte). Puis LA preuve de constructibilité : écris
`simule_construction.py` (dans le scratchpad, pas dans le dépôt) qui, avec les fonctions de `scripts/plan_lanes.py`
sur l'ensemble des plans touchés, coche en mémoire les tâches que le planificateur autorise, recommence jusqu'au point
fixe, et liste les tâches de la vague JAMAIS autorisées — il ne doit rester que les GATED et ce qui dépend d'elles ou
d'une tâche `[BLOCKED]` déjà au plan ; toute autre tâche bloquée est un défaut d'ordre à corriger (dans la copie
d'édition ET dans le plan) ou à me signaler précisément. Relance `coherence_vague.py` si tu as touché une copie
d'édition. Une garde rouge se corrige à la cause ; ne modifie aucune garde, aucune liste d'exceptions.

## Livraison
Commits sur `claude/calepinage-vague2` (message en français, terminé par la ligne
`Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`), `git push origin claude/calepinage-vague2` (jamais de
force). Mets à jour le titre et le corps de la PR #1517 (`gh pr edit 1517`) : décompte réel, ce qui a changé depuis
la première intégration, les trois gestes du fondateur, « docs seulement, rien construit » ; le corps se termine par
la ligne `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Ne merge pas, n'active pas l'auto-merge.
Sauvegarde tes scripts dans `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\l5\integ2\`.

## Compte rendu (45 lignes au plus)
Décompte final (total, par plan, par section, GATED un par un avec leur condition). Ce que tu as fait d'ACAL487.
Dernière ligne de CHAQUE garde. `plan_lanes` : refus par plan, main → branche, avec l'explication. La simulation de
construction : nombre de passes, tâches jamais autorisées et pourquoi, la liste `--only` de la vague 0. Toute
correction que tu as dû faire dans une copie d'édition. SHA du dernier commit poussé. Ce que tu n'as pas vérifié.
