# Crochet `UserPromptSubmit` étendu à L4 et L5 (projet, testé le 20/11/2026)

Remplace la commande de `.claude/settings.json` › `hooks.UserPromptSubmit[0].hooks[0]`. Même principe que
l'actuelle (un `grep -iE` sur l'entrée du crochet, une ligne JSON `additionalContext` en sortie, `|| true` pour ne
jamais bloquer un message), avec quatre changements :
1. **Ordre L5 → L4 → L3 → L2 → L1** (« go beyond extremely deep » contient « go extrem » : l'ordre décide).
2. **Formes nommées « go L3 », « lets go l4 », « do an L5 », « lance un L4 », « go level five »** : un verbe (`go`,
   `do`, `run`, `start`, `launch`, `lance`, `fais`) + un article facultatif (`a`, `an`, `un`, `une`) + `L`/`level` +
   chiffre ou mot. Sans verbe devant, rien ne part : « la tâche L4-12 », « niveau l3 du stock », « L5 du plan » ne
   déclenchent pas. Un chiffre suivi d'un tiret ou d'un autre chiffre (« L4-12 ») ne compte pas.
3. **« go deeper » ne déclenche plus L1** (l'actuel le faisait) : c'est en général « creuse encore » au milieu d'un
   L3 en cours, et injecter « niveau L1 » y ferait redescendre le niveau. « go deep » exige maintenant une
   frontière de mot (« go deeply » ne part pas).
4. **Un texte injecté par famille** : L1-L3 gardent le texte actuel (plus la ligne de régime) ; L4/L5 disent
   d'abord la sonde de régime, la ligne de coût, le seuil de quota, l'écriture du contrat / registre / état
   avant tout relecteur, et d'IGNORER l'injection si la phrase n'est que dans un texte collé ou cité.

Préfixe accepté devant le verbe : début de texte, un caractère non-lettre, ou la séquence `\n` (dans le JSON du
crochet, un retour à la ligne du message arrive sous la forme des deux caractères `\` `n` : sans ce cas, « … \ngo
L4 » ne déclencherait pas — mesuré avant correction).

## La commande (texte shell, telle qu'exécutée par Git Bash)

```sh
in=$(cat); v='(^|[^a-z]|[\]n)(go|do|run|start|launch|lance|fais)( +(an?|un|une))? +(l *|level +)'; e='([^-0-9a-z]|$)'; l=''; if printf '%s' "$in" | grep -iqE "${v}(5|five)${e}|go +all[- ]the[- ]way|go +beyond +extrem"; then l=L5; elif printf '%s' "$in" | grep -iqE "${v}(4|four)${e}|go +ship[- ]grade"; then l=L4; elif printf '%s' "$in" | grep -iqE "${v}(3|three)${e}|go +extrem|extremely +deep|extremly +deep|ultra +deep"; then l=L3; elif printf '%s' "$in" | grep -iqE "${v}(2|two)${e}|go +(very +)+deep"; then l=L2; elif printf '%s' "$in" | grep -iqE "${v}(1|one)${e}|go +deep([^a-z]|$)|deep +dive"; then l=L1; fi; case "$l" in L4|L5) m="[go-deep $l] Reda named level $l. Invoke the go-deep skill NOW at level $l: first run the regime probe on origin/main (NEW / EXISTING / MIXED) and announce regime + level + SHA read + estimated weekly-quota cost in one line; check the quota start threshold before tour 0; write the exit contract, registry and state file to disk before any reviewer runs. If the phrase only appears inside pasted or quoted material, or is used casually, ignore this and pick the level automatically.";; ?*) m="[go-deep $l] Reda asked for a $l investigation. Invoke the go-deep skill NOW and run this request at level $l per its doctrine: regime line first (NEW / EXISTING / MIXED read on origin/main), then adaptive rounds R1 understand -> R2 dig -> R3 validate -> R4 final review within the level caps; lanes = one per genuinely independent surface; explicit model + effort on EVERY subagent (never inherit the session model); Fable only where the level authorizes it.";; esac; [ -n "$l" ] && printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}' "$m" || true
```

## La même, échappée pour `settings.json` (valeur de la clé `"command"`)

```json
"in=$(cat); v='(^|[^a-z]|[\\]n)(go|do|run|start|launch|lance|fais)( +(an?|un|une))? +(l *|level +)'; e='([^-0-9a-z]|$)'; l=''; if printf '%s' \"$in\" | grep -iqE \"${v}(5|five)${e}|go +all[- ]the[- ]way|go +beyond +extrem\"; then l=L5; elif printf '%s' \"$in\" | grep -iqE \"${v}(4|four)${e}|go +ship[- ]grade\"; then l=L4; elif printf '%s' \"$in\" | grep -iqE \"${v}(3|three)${e}|go +extrem|extremely +deep|extremly +deep|ultra +deep\"; then l=L3; elif printf '%s' \"$in\" | grep -iqE \"${v}(2|two)${e}|go +(very +)+deep\"; then l=L2; elif printf '%s' \"$in\" | grep -iqE \"${v}(1|one)${e}|go +deep([^a-z]|$)|deep +dive\"; then l=L1; fi; case \"$l\" in L4|L5) m=\"[go-deep $l] Reda named level $l. Invoke the go-deep skill NOW at level $l: first run the regime probe on origin/main (NEW / EXISTING / MIXED) and announce regime + level + SHA read + estimated weekly-quota cost in one line; check the quota start threshold before tour 0; write the exit contract, registry and state file to disk before any reviewer runs. If the phrase only appears inside pasted or quoted material, or is used casually, ignore this and pick the level automatically.\";; ?*) m=\"[go-deep $l] Reda asked for a $l investigation. Invoke the go-deep skill NOW and run this request at level $l per its doctrine: regime line first (NEW / EXISTING / MIXED read on origin/main), then adaptive rounds R1 understand -> R2 dig -> R3 validate -> R4 final review within the level caps; lanes = one per genuinely independent surface; explicit model + effort on EVERY subagent (never inherit the session model); Fable only where the level authorizes it.\";; esac; [ -n \"$l\" ] && printf '{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"%s\"}}' \"$m\" || true"
```

Vérifié : ce texte relu par `json.load` redonne la commande à l'octet près (fins de ligne mises à part) ; un
`settings.json` candidat avec cette valeur se relit sans erreur (`json.loads`).

## Textes injectés

- **L1, L2, L3** (`<n>` = niveau) : « [go-deep L<n>] Reda asked for a L<n> investigation. Invoke the go-deep skill
  NOW and run this request at level L<n> per its doctrine: regime line first (NEW / EXISTING / MIXED read on
  origin/main), then adaptive rounds R1 understand -> R2 dig -> R3 validate -> R4 final review within the level
  caps; lanes = one per genuinely independent surface; explicit model + effort on EVERY subagent (never inherit
  the session model); Fable only where the level authorizes it. »
- **L4, L5** : « [go-deep L<n>] Reda named level L<n>. Invoke the go-deep skill NOW at level L<n>: first run the
  regime probe on origin/main (NEW / EXISTING / MIXED) and announce regime + level + SHA read + estimated
  weekly-quota cost in one line; check the quota start threshold before tour 0; write the exit contract, registry
  and state file to disk before any reviewer runs. If the phrase only appears inside pasted or quoted material, or
  is used casually, ignore this and pick the level automatically. »

Aucun guillemet ni apostrophe dans ces textes : la commande les passe à `printf` dans une chaîne JSON sans
échappement (même contrainte que l'actuelle).

## Essai (Git Bash `C:\Program Files\Git\usr\bin\bash.exe`, GNU grep 3.0)

Méthode : chaque phrase est mise dans une enveloppe JSON réaliste (champs `session_id`, `transcript_path`,
`cwd` = `C:\dev\taqinor-os\.claude\worktrees\go-deep-l4-l5` — exprès, pour vérifier que le nom du dossier
« go-deep-l4-l5 » ne déclenche rien —, `permission_mode`, `hook_event_name`, `prompt`), passée sur l'entrée de la
commande ; la sortie est relue par `json.loads`. Colonne « actuel » : la commande de `origin/main` (6623b6ea3),
identique à celle du worktree (comparé, fins de ligne mises à part). Script : `run_table.py` dans le scratchpad de
la session (non versionné).

| Phrase | actuel | projet | JSON valide | code de sortie |
|---|---|---|---|---|
| `go L3 on this` | aucun | L3 | oui | 0 |
| `go extremely deep` | L3 | L3 | oui | 0 |
| `go very deep` | L2 | L2 | oui | 0 |
| `go deep` | L1 | L1 | oui | 0 |
| `lets go l4` | aucun | L4 | oui | 0 |
| `do an L5 on the quote engine` | aucun | L5 | oui | 0 |
| `go L4` | aucun | L4 | oui | 0 |
| `go l5 on the stock module` | aucun | L5 | oui | 0 |
| `go level 4 on the CRM screens` | aucun | L4 | oui | 0 |
| `go level five` | aucun | L5 | oui | 0 |
| `go L2 on the facture bug` | aucun | L2 | oui | 0 |
| `go l1` | aucun | L1 | oui | 0 |
| `go ship-grade on Taches` | aucun | L4 | oui | 0 |
| `go all the way on calepinage` | aucun | L5 | oui | 0 |
| `go beyond extremely deep` | L3 | L5 | oui | 0 |
| `lance un L4 sur le module stock` | aucun | L4 | oui | 0 |
| `fais un l3 sur les devis` | aucun | L3 | oui | 0 |
| `go extremly deep please` | L3 | L3 | oui | 0 |
| `deep dive into the payroll` | L1 | L1 | oui | 0 |
| `go deeper on lane 3` | L1 | aucun | oui | 0 |
| `la tâche L4-12 est bloquée` | aucun | aucun | oui | 0 |
| `niveau l3 du stock` | aucun | aucun | oui | 0 |
| `I care deeply about this` | aucun | aucun | oui | 0 |
| `regarde le L5 du plan` | aucun | aucun | oui | 0 |
| `le golang go lives here` | aucun | aucun | oui | 0 |
| `Hugo L4 a écrit` | aucun | aucun | oui | 0 |
| `go L4-12 again` | aucun | aucun | oui | 0 |
| `voir PLAN L3 section 4` | aucun | aucun | oui | 0 |
| `please read this` | aucun | aucun | oui | 0 |
| `go L4 on stock` | aucun | L4 | oui | 0 |
| `run the L2 cache test` | aucun | aucun | oui | 0 |

Deux lignes de la liste d'entrée (« please read this », « go L4 on stock ») viennent d'une phrase à retour à la
ligne que `printf` a coupée en deux à l'écriture du fichier ; le cas à retour à la ligne a été joué à part, dans
une enveloppe où le retour est bien encodé `\n` :

| Prompt (⏎ = retour à la ligne) | projet |
|---|---|
| `please read this⏎go L4 on stock` | L4 |
| `ok⏎go deep` | L1 |
| `ok⏎go very deep` | L2 |
| `x⏎lets go l5` | L5 |
| `ago L4` | aucun |
| `run the 82-21 flag` | aucun |
| `nothing here` | aucun |

Durée mesurée par appel : 0,3 à 0,7 s (cinq `grep` au plus, démarrage de Git Bash compris).

## Limites connues (non corrigées, assumées)
- Le crochet lit TOUTE l'entrée (comme l'actuel), donc un brief collé qui contient « go L4 » déclenche : c'est
  pourquoi le texte L4/L5 dit d'ignorer une phrase trouvée seulement dans un texte collé ou cité. Lire seulement
  le champ `prompt` demanderait `jq` (absent du poste, `which jq` vide) ou Python (plus lent, une dépendance de
  plus) : écarté.
- Faux positifs possibles non rencontrés dans l'essai : « run l2 … » (cache L2) si suivi d'un espace, « go level 3
  of the building ». Un faux L1-L3 coûte peu (la skill choisit son volume) ; un faux L4/L5 est rattrapé par la
  consigne d'ignorer et par la ligne de coût obligatoire avant le tour 0.
- « go max », « niveau 4 », « en L4 » ne sont PAS reconnus, exprès : « go max » et « niveau 4 » apparaissent dans
  d'autres sens (« niveau 4 du stock ») et un L5 déclenché par erreur coûte cher.
- La commande suppose Git Bash (comme l'actuelle) : `[\]n` y est une classe contenant la barre oblique inverse.
