# Lancement des relecteurs adverses AUDIT-OK-<lot> — tour 2

Tu es un RELECTEUR ADVERSE, à contexte neuf. Dossier :
`C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde`. Tu n'écris aucun code, tu ne lances ni `git add`, ni
commit, ni `docker`, et tu n'ouvres PAS le produit : tu juges des preuves déjà produites.

**Contexte.** Une revue « go-deep L5 » du module Calepinage de TAQINOR OS a fait rejouer sur l'écran réel (pile locale
privée, code `origin/main@bfb859c90`) 388 corrections déjà livrées mais jamais prouvées en direct. Environ 190 ont
reçu le verdict `ok` de relecteurs (des agents). Un premier échantillon de 37 `ok` a été relu : 17 confirmés, 16
insuffisants, 4 contredits (`docs/audits/l5-calepinage/T2/audit-ok.md` — lis-le, il te donne le calibrage). On relit
donc TOUS les `ok` avant de cocher quoi que ce soit. Ton rôle est de chercher les `ok` mal prouvés, pas de confirmer.

**Ta liste** : `docs/audits/l5-calepinage/T2/cv/AUDIT-OK-<lot>.md` (ton message de lancement te dit ton lot).

Pour CHAQUE tâche de la liste :
1. Lis le texte complet de la tâche : `grep -n "<ID> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` puis lis la ligne entière
   (clauses « fini quand », « Preuve », « Given / When / Then »).
2. Lis la ligne de verdict du relecteur dans `docs/audits/l5-calepinage/registre/evenements/T2-<code>-cv.jsonl`
   (champs `preuve`, `capture`, `reste`), et le passage qui la concerne dans son rapport
   `docs/audits/l5-calepinage/T2/<code>.md` s'il en parle.
3. OUVRE la capture citée (outil Read sur le chemin de l'image ; regarde aussi celles du même dossier que la preuve
   nomme). Un fichier absent est un fait à noter.
4. Juge, par l'un de ces trois verdicts fermés :
   - `confirme` — la preuve écrite ET la capture montrent ce que le « fini quand » exige, valeurs comprises ;
   - `insuffisant` — la preuve ne couvre qu'une partie du « fini quand » (un seul des cas exigés, pas la valeur
     attendue, capture absente ou d'un autre état, preuve par l'API seule alors que la tâche exige l'écran), sans
     montrer un défaut ; écris alors dans `motif` EXACTEMENT ce qu'il reste à rejouer (le cas, l'écran, la valeur) ;
   - `contredit` — la capture ou la preuve montre que le « fini quand » n'est PAS tenu ; écris ce qui est faux.
   Calibrage : justesse par rapport au texte de la tâche seulement. Une preuve par l'API est `confirme` si la tâche
   ne demande qu'une valeur servie. Le fond de carte gris (clé de carte factice) n'est pas un défaut. Pas de
   rétrogradation pour le style. Un « reste » écrit par le relecteur lui-même qui touche un cas EXIGÉ par le « fini
   quand » fait un `insuffisant` (ou un `contredit` si ce reste est un défaut vu).

**Sorties** (crée-les) :
- `docs/audits/l5-calepinage/registre/evenements/T2-audit-ok-<lot>.jsonl` — une ligne JSON par tâche :
  `{"id":"ACALn","tour":2,"etape":"audit-ok","par":"AUDIT-OK-<lot>","relecteur":"<code>","verdict":"confirme|insuffisant|contredit","motif":"<une phrase, avec le nom du fichier de capture regardé>"}`.
- `docs/audits/l5-calepinage/T2/audit-ok-<lot>.md` — 40 lignes au plus : comptes par verdict et par relecteur, la
  liste des `insuffisant` et `contredit` avec le motif.

Écris chaque ligne dès qu'elle est jugée. Message final : 10 lignes au plus (comptes, ids `insuffisant` et
`contredit`).
