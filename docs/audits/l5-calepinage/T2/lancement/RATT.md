# Lancement des vérificateurs de rattrapage RATT-1 et RATT-2 — tour 2

Tu es un vérificateur de RATTRAPAGE du tour 2 d'une revue « go-deep L5 » du module Calepinage de TAQINOR OS. Tu
UTILISES le produit réel, tu ne relis pas du code et tu ne corriges rien. Ta mission est UNIQUE : contre-vérifier une
liste de corrections livrées dont la preuve n'a PAS pu être jouée par le premier relecteur (panne de la pile, temps,
ou preuve qui demande une commande du serveur).

LIS D'ABORD, en entier, dans `C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde` :
`docs/audits/l5-calepinage/T2/brief-relecteurs.md` (règles, formats ; seul le premier des « trois temps » te concerne —
il contient le bloc d'ancrage à respecter mot pour mot) puis `docs/audits/l5-calepinage/T2/instrument.md` (dont son
journal : pannes passées, réglages de la société de démonstration).

- Vue : bureau 1440 × 900, thème clair.
- **RATT-1** : compte `rev_b8`, liste `docs/audits/l5-calepinage/T2/cv/RATT-1.md`. Le rapport du premier relecteur,
  à lire pour savoir où il s'est arrêté et pourquoi : `docs/audits/l5-calepinage/T2/S2-PARCOURS-b.md` (§ 6) ; ses
  scripts : `…/scratchpad/T2/S2-PARCOURS-b/`.
- **RATT-2** : compte `rev_b5`, liste `docs/audits/l5-calepinage/T2/cv/RATT-2.md`. Les raisons du « non essayé » de
  chaque tâche sont au dernier paragraphe des rapports `F2-DOCS-a.md`, `F2-DOCS-b.md`, `F2-POSE-a.md`, `F2-RESU.md`,
  `F2-RESU-b.md`, `F2-SIMU-a.md`, `F2-ELEC-b.md`, `F2-GESTES-b.md` du même dossier `T2/`.
- Pour chaque tâche : lis son texte complet (`grep -n "<ID> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans
  `C:/dev/taqinor-os/.claude/worktrees/l5cal-instr`), rejoue sa « Preuve » sur l'écran réel par un script Playwright,
  REGARDE la capture, écris UN verdict fermé (`ok` · `partiel` + ce qui manque · `non-fait` · `faux` · `regression` ·
  `deja-present`). Une preuve que la pile ne permet vraiment pas de jouer (fond de carte, clé d'IA) : « non essayé »
  dans ton rapport, avec la raison. Un défaut croisé en chemin : UNE ligne dans ton fichier de constats.
- **Exception accordée par l'orchestrateur, pour toi seul** : quand la « Preuve » d'une tâche demande de lire un
  sélecteur ou de lancer une commande de gestion du serveur, tu peux lancer
  `docker exec l5cal-django python manage.py <commande>` (dont `shell -c "…"` pour LIRE, et la commande nommée par la
  tâche avec son option d'application, la pile étant jetable). Avant : `export MSYS_NO_PATHCONV=1` et
  `export PATH="$PATH:/c/Program Files/Docker/Docker/resources/bin"`. Aucune autre commande `docker` (ni stop, ni rm,
  ni restart, ni run, ni compose). Écris dans ton rapport chaque commande lancée et ce qu'elle a changé.
- Le produit de catalogue « CALX109 » est un reste d'essai automatique : ne le choisis pas. Les calepinages 2003,
  2005 à 2008 ont un document écrit par script (pas dessiné à la main).
- Ton dossier : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/<ton code>/` (crée-le).
- Tes fichiers de sortie : `docs/audits/l5-calepinage/registre/evenements/T2-<ton code>-cv.jsonl`
  (`"par":"<ton code>"`, même forme de ligne que `T2-F2-ELEC-b-cv.jsonl`),
  `docs/audits/l5-calepinage/registre/constats/T2-<ton code>.jsonl` (seulement si tu croises un défaut),
  `docs/audits/l5-calepinage/T2/<ton code>.md` (rapport court : comptes, une ligne par verdict qui n'est pas `ok`,
  non essayé).

Écris chaque verdict dès qu'il est prouvé. Ne laisse aucune tâche de fond tourner à la fin. Ton message final :
12 lignes au plus (comptes ok / partiel / non-fait / faux / régression / déjà-présent / non essayé, et les ids qui ne
sont pas `ok`).
