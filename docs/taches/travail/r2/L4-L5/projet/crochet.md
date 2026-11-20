# Crochet `UserPromptSubmit` étendu à L4 et L5 (corrigé R2-bis, rejoué le 20/11/2026)

Remplace la valeur `hooks.UserPromptSubmit[0].hooks[0].command` de `.claude/settings.json` ; rien d'autre ne change
dans ce fichier. Même style que l'actuelle : Git Bash, `grep -iE` sur l'entrée JSON du crochet, une ligne JSON
`additionalContext` en sortie, `|| true` pour ne jamais bloquer un message, sans `jq` (absent du poste).

## Ce qui change par rapport au projet R2 (décision « maison C1 » du tri)
1. **Verbes réduits à `go`, `do`, `lance`, `fais`** (+ article facultatif `a`, `an`, `un`, `une`) devant `L<chiffre>` ou
   `level <chiffre | mot>`. `run`, `start`, `launch` sont retirés : les lanes s'appellent L1-L8 ici (« start L5 now,
   the lane L4 is done », « run L4 again » déclenchaient à tort).
2. **Tous les niveaux cités sont relevés** (un `grep -o` unique, chiffres ramenés par `sed`), jamais le premier
   trouvé dans l'ordre L5 → L1 : un niveau plus haut cité ailleurs ne l'emporte plus sur celui que Reda demande.
3. **Texte NEUTRE** dès que deux niveaux différents sont cités, ou, quand L4 / L5 est cité, dès qu'une question, une
   citation, une négation ou une réserve figure dans le message (`?`, guillemets, « not / pas / jamais / should /
   maybe / recommand… »). Le texte neutre ne lance AUCUN niveau : il dit de lire la phrase de Reda, de suivre le niveau
   qu'il demande en ses propres mots, sinon le choix automatique L1-L3, et de ne jamais partir en L4 / L5 sur ce seul
   signal.
4. Un seul niveau, sans ambiguïté : le texte de sa famille, comme au projet. Le texte L4 / L5 dit en plus de lire
   `L4.md` (ou `L5.md`) en entier avant le tour 0.
5. « go all the way » ne compte que suivi de « on / sur », d'une ponctuation ou de la fin du message (« let's go all
   the way down the list » ne part plus). « go beyond extremely deep » contient « extremely deep » : il donne L3 (comme
   l'actuel) et non plus L5. « go deeper » ne déclenche plus L1 (inchangé depuis le projet). Les mots de nombre
   (`one` … `five`) ne valent qu'après `level` (« go lone wolf » ne donne plus L1).
6. Pas de `sort` (sous Windows un `sort.exe` du système peut le masquer) : dédoublonnage par une boucle `case`.

## La commande, forme lisible (même comportement : la table ci-dessous a été jouée sur les deux formes)
```sh
in=$(cat)
# v : un niveau NOMMÉ = verbe (go | do | lance | fais) + article facultatif + « L<chiffre> » ou « level <chiffre|mot> »,
#     précédé d'un début, d'un non-alphanumérique ou de la séquence \n du JSON, et non suivi d'un tiret ou d'un chiffre
v='(^|[^a-z0-9]|[\]n)(go|do|lance|fais)( +(an?|un|une))? +(l *[1-5]|level +([1-5]|one|two|three|four|five))([^-0-9a-z]|$)'
# f : les formes en mots (L4, L5, puis celles de l'actuel pour L3, L2, L1)
f='go +ship[- ]grade|go +all[- ]the[- ]way( +(on|sur) |[.!,;]|[\]n|"|$)|go +extrem|extremely +deep|extremly +deep|ultra +deep|go +(very +)+deep|go +deep([^a-z]|$)|deep +dive'
# n : TOUS les niveaux cités, un chiffre par occurrence
n=" $(printf '%s' "$in" | grep -ioE "$v|$f" | tr 'A-Z' 'a-z' | sed -E 's/.*ship.*/4/; s/.*all.*/5/; s/.*(extrem|ultra).*/3/; s/.*very.*/2/; s/.*deep.*/1/; s/.*(l *|level +)//; s/^one.*/1/; s/^two.*/2/; s/^three.*/3/; s/^four.*/4/; s/^five.*/5/; s/^([1-5]).*/\1/' | tr '\n' ' ')"
# u : les niveaux DISTINCTS (sans sort : aucun risque de prendre le sort.exe de Windows) ; s : leur liste « L3 L5 »
u=''; s=''
for d in 1 2 3 4 5; do case "$n" in *" $d "*) u="$u$d"; s="${s}L$d ";; esac; done
# w : si L4 ou L5 est cité, une question, une citation, une négation ou une réserve rend le signal ambigu
w=''
case "$u" in *4*|*5*) printf '%s' "$in" | grep -iqE '[?]|[\]"|«|»|“|”|[\]u00ab|[\]u00bb|[\]u201[cd]|(^|[^a-z]|[\]n)(don.?t|do +not|not|never|pas|jamais|should|shall|would|could|might|maybe|perhaps|faudrait|devrait|serait)([^a-z]|$)|peut-|recommand|recommend|suggest|propos' && w=1;; esac
m=''
if [ ${#u} = 1 ] && [ -z "$w" ]; then
  l="L$u"
  case "$l" in
    L4|L5) m="[go-deep $l] Reda named level $l. Invoke the go-deep skill NOW at level $l and read its file $l.md in full before tour 0: run the regime probe on origin/main (NEW / EXISTING / MIXED), read the weekly quota, announce regime + level + SHA read + cost line in one line, and write the exit contract, registry and state file to disk before any reviewer runs. If the phrase only appears inside pasted or quoted material, ignore this and pick the level automatically (L1-L3).";;
    *) m="[go-deep $l] Reda asked for a $l investigation. Invoke the go-deep skill NOW and run this request at level $l per its doctrine: regime line first (NEW / EXISTING / MIXED read on origin/main), then adaptive rounds R1 understand -> R2 dig -> R3 validate -> R4 final review within the level caps; lanes = one per genuinely independent surface; explicit model + effort on EVERY subagent (never inherit the session model); Fable only where the level authorizes it.";;
  esac
elif [ -n "$u" ]; then
  m="[go-deep] Levels cited: ${s}- several levels, or a negation, question, hedge or quote next to an L4/L5. This hook starts NO level. Read Reda own sentence: run the level he plainly asks for in his own words; if none is plain, auto-pick L1-L3 per the go-deep skill and propose L4/L5 once with their cost. Never start L4 or L5 on this signal alone."
fi
[ -n "$m" ] && printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}' "$m" || true
```

## La même sur une ligne, telle qu'exécutée
```sh
in=$(cat); v='(^|[^a-z0-9]|[\]n)(go|do|lance|fais)( +(an?|un|une))? +(l *[1-5]|level +([1-5]|one|two|three|four|five))([^-0-9a-z]|$)'; f='go +ship[- ]grade|go +all[- ]the[- ]way( +(on|sur) |[.!,;]|[\]n|"|$)|go +extrem|extremely +deep|extremly +deep|ultra +deep|go +(very +)+deep|go +deep([^a-z]|$)|deep +dive'; n=" $(printf '%s' "$in" | grep -ioE "$v|$f" | tr 'A-Z' 'a-z' | sed -E 's/.*ship.*/4/; s/.*all.*/5/; s/.*(extrem|ultra).*/3/; s/.*very.*/2/; s/.*deep.*/1/; s/.*(l *|level +)//; s/^one.*/1/; s/^two.*/2/; s/^three.*/3/; s/^four.*/4/; s/^five.*/5/; s/^([1-5]).*/\1/' | tr '\n' ' ')"; u=''; s=''; for d in 1 2 3 4 5; do case "$n" in *" $d "*) u="$u$d"; s="${s}L$d ";; esac; done; w=''; case "$u" in *4*|*5*) printf '%s' "$in" | grep -iqE '[?]|[\]"|«|»|“|”|[\]u00ab|[\]u00bb|[\]u201[cd]|(^|[^a-z]|[\]n)(don.?t|do +not|not|never|pas|jamais|should|shall|would|could|might|maybe|perhaps|faudrait|devrait|serait)([^a-z]|$)|peut-|recommand|recommend|suggest|propos' && w=1;; esac; m=''; if [ ${#u} = 1 ] && [ -z "$w" ]; then l="L$u"; case "$l" in L4|L5) m="[go-deep $l] Reda named level $l. Invoke the go-deep skill NOW at level $l and read its file $l.md in full before tour 0: run the regime probe on origin/main (NEW / EXISTING / MIXED), read the weekly quota, announce regime + level + SHA read + cost line in one line, and write the exit contract, registry and state file to disk before any reviewer runs. If the phrase only appears inside pasted or quoted material, ignore this and pick the level automatically (L1-L3).";; *) m="[go-deep $l] Reda asked for a $l investigation. Invoke the go-deep skill NOW and run this request at level $l per its doctrine: regime line first (NEW / EXISTING / MIXED read on origin/main), then adaptive rounds R1 understand -> R2 dig -> R3 validate -> R4 final review within the level caps; lanes = one per genuinely independent surface; explicit model + effort on EVERY subagent (never inherit the session model); Fable only where the level authorizes it.";; esac; elif [ -n "$u" ]; then m="[go-deep] Levels cited: ${s}- several levels, or a negation, question, hedge or quote next to an L4/L5. This hook starts NO level. Read Reda own sentence: run the level he plainly asks for in his own words; if none is plain, auto-pick L1-L3 per the go-deep skill and propose L4/L5 once with their cost. Never start L4 or L5 on this signal alone."; fi; [ -n "$m" ] && printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}' "$m" || true
```

## La valeur JSON pour `.claude/settings.json` (clé `"command"`)
```json
"in=$(cat); v='(^|[^a-z0-9]|[\\]n)(go|do|lance|fais)( +(an?|un|une))? +(l *[1-5]|level +([1-5]|one|two|three|four|five))([^-0-9a-z]|$)'; f='go +ship[- ]grade|go +all[- ]the[- ]way( +(on|sur) |[.!,;]|[\\]n|\"|$)|go +extrem|extremely +deep|extremly +deep|ultra +deep|go +(very +)+deep|go +deep([^a-z]|$)|deep +dive'; n=\" $(printf '%s' \"$in\" | grep -ioE \"$v|$f\" | tr 'A-Z' 'a-z' | sed -E 's/.*ship.*/4/; s/.*all.*/5/; s/.*(extrem|ultra).*/3/; s/.*very.*/2/; s/.*deep.*/1/; s/.*(l *|level +)//; s/^one.*/1/; s/^two.*/2/; s/^three.*/3/; s/^four.*/4/; s/^five.*/5/; s/^([1-5]).*/\\1/' | tr '\\n' ' ')\"; u=''; s=''; for d in 1 2 3 4 5; do case \"$n\" in *\" $d \"*) u=\"$u$d\"; s=\"${s}L$d \";; esac; done; w=''; case \"$u\" in *4*|*5*) printf '%s' \"$in\" | grep -iqE '[?]|[\\]\"|«|»|“|”|[\\]u00ab|[\\]u00bb|[\\]u201[cd]|(^|[^a-z]|[\\]n)(don.?t|do +not|not|never|pas|jamais|should|shall|would|could|might|maybe|perhaps|faudrait|devrait|serait)([^a-z]|$)|peut-|recommand|recommend|suggest|propos' && w=1;; esac; m=''; if [ ${#u} = 1 ] && [ -z \"$w\" ]; then l=\"L$u\"; case \"$l\" in L4|L5) m=\"[go-deep $l] Reda named level $l. Invoke the go-deep skill NOW at level $l and read its file $l.md in full before tour 0: run the regime probe on origin/main (NEW / EXISTING / MIXED), read the weekly quota, announce regime + level + SHA read + cost line in one line, and write the exit contract, registry and state file to disk before any reviewer runs. If the phrase only appears inside pasted or quoted material, ignore this and pick the level automatically (L1-L3).\";; *) m=\"[go-deep $l] Reda asked for a $l investigation. Invoke the go-deep skill NOW and run this request at level $l per its doctrine: regime line first (NEW / EXISTING / MIXED read on origin/main), then adaptive rounds R1 understand -> R2 dig -> R3 validate -> R4 final review within the level caps; lanes = one per genuinely independent surface; explicit model + effort on EVERY subagent (never inherit the session model); Fable only where the level authorizes it.\";; esac; elif [ -n \"$u\" ]; then m=\"[go-deep] Levels cited: ${s}- several levels, or a negation, question, hedge or quote next to an L4/L5. This hook starts NO level. Read Reda own sentence: run the level he plainly asks for in his own words; if none is plain, auto-pick L1-L3 per the go-deep skill and propose L4/L5 once with their cost. Never start L4 or L5 on this signal alone.\"; fi; [ -n \"$m\" ] && printf '{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"%s\"}}' \"$m\" || true"
```
Vérifié dans cette session : `json.loads` de cette valeur redonne la commande d'une ligne à l'octet près ; un objet
`{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":<valeur>}]}]}}` se relit sans erreur et en redonne la
même commande, qui est celle qu'a jouée la table. Les guillemets `« » “ ”` de la commande restent en UTF-8 dans le
fichier (JSON valide).

## Textes injectés
- **L1, L2, L3** : « [go-deep L<n>] Reda asked for a L<n> investigation. Invoke the go-deep skill NOW and run this
  request at level L<n> per its doctrine: regime line first (NEW / EXISTING / MIXED read on origin/main), then adaptive
  rounds R1 understand -> R2 dig -> R3 validate -> R4 final review within the level caps; lanes = one per genuinely
  independent surface; explicit model + effort on EVERY subagent (never inherit the session model); Fable only where
  the level authorizes it. »
- **L4, L5** : « [go-deep L<n>] Reda named level L<n>. Invoke the go-deep skill NOW at level L<n> and read its file
  L<n>.md in full before tour 0: run the regime probe on origin/main (NEW / EXISTING / MIXED), read the weekly quota,
  announce regime + level + SHA read + cost line in one line, and write the exit contract, registry and state file to
  disk before any reviewer runs. If the phrase only appears inside pasted or quoted material, ignore this and pick the
  level automatically (L1-L3). »
- **Neutre** : « [go-deep] Levels cited: L<x> L<y> - several levels, or a negation, question, hedge or quote next to an
  L4/L5. This hook starts NO level. Read Reda own sentence: run the level he plainly asks for in his own words; if none
  is plain, auto-pick L1-L3 per the go-deep skill and propose L4/L5 once with their cost. Never start L4 or L5 on this
  signal alone. »
Aucun `"` ni `\` dans ces textes : la commande les passe à `printf` dans une chaîne JSON sans échappement.

## Essai rejoué dans cette session (Git Bash `C:\Program Files\Git\bin\bash.exe`, GNU bash 5.2.37, GNU grep 3.0)
Méthode : chaque phrase est mise dans une enveloppe JSON réaliste (`session_id`, `transcript_path`, `cwd` =
`C:\dev\taqinor-os\.claude\worktrees\go-deep-l4-l5` — pour vérifier que ce nom de dossier ne déclenche rien —,
`permission_mode`, `hook_event_name`, `prompt` en dernier), encodée DEUX fois (`json.dumps` avec et sans
`ensure_ascii`, donc accents et guillemets bruts ou en `\uXXXX`) ; la commande est celle relue depuis la valeur JSON
ci-dessus ; la sortie est relue par `json.loads`. « Conforme » = même résultat sous les deux encodages, code de sortie
0, JSON valide, et résultat dans la colonne « acceptable ». Colonne « actuel » : la commande de `origin/main`
(81899193d). `N` = texte neutre, `-` = rien. Script : `run_table.py` dans le scratchpad de la session (non versionné).

Sources des phrases : `maison` = les 29 phrases du tableau de `validation/maison.md` § 1 (les deux « rapports collés »
y sont décrits, pas cités : ils sont reconstitués ici en texte de plusieurs lignes) ; `projet` = les 38 lignes du
tableau du projet R2 (31 + 7 à retour de ligne ; `faits.md` en compte 40 dont ces 38) ; `ajout` = 5 phrases du
correcteur sur les risques de la nouvelle forme.

| # | source | phrase (⏎ = retour à la ligne) | actuel | nouveau | acceptable | conforme |
|---|---|---|---|---|---|---|
| 1 | maison | `go L3 on this` | - | L3 | L3 | oui |
| 2 | maison | `lets learn from what we did here and make it an L4 or l5, but befor...` | - | L3 | L3 | oui |
| 3 | maison | `go L3 on this⏎⏎--- rapport colle ---⏎Verdict : partiel.⏎we should g...` | L1 | N | L3/N | oui |
| 4 | maison | `voici le rapport :⏎il faut go deeper sur la lane 3 ; un L5 serait e...` | L1 | - | - | oui |
| 5 | maison | `voici le rapport :⏎## Verdict⏎Recommandation : go L5 sur le module ...` | - | N | -/N | oui |
| 6 | maison | `ACHT22 est rouge` | - | - | - | oui |
| 7 | maison | `CAL51 reste gate ?` | - | - | - | oui |
| 8 | maison | `la tache L4-12 est bloquee` | - | - | - | oui |
| 9 | maison | `go L4-12 again` | - | - | - | oui |
| 10 | maison | `niveau 4 sur le stock` | - | - | - | oui |
| 11 | maison | `va tres profond sur les devis` | - | - | - | oui |
| 12 | maison | `fais un L4 sur le module stock` | - | L4 | L4 | oui |
| 13 | maison | `ok⏎go L4 on stock` | - | L4 | L4 | oui |
| 14 | maison | `go l5` | - | L5 | L5 | oui |
| 15 | maison | `go L 4` | - | L4 | L4 | oui |
| 16 | maison | `` | - | - | - | oui |
| 17 | maison | `il a ecrit "go L4" dans son message⏎et puis rien` | - | N | -/N | oui |
| 18 | maison | `start L5 now, the lane L4 is done` | - | - | - | oui |
| 19 | maison | `run L4 again, it failed on flake8` | - | - | - | oui |
| 20 | maison | `launch L3 and L4 in parallel` | - | - | -/N | oui |
| 21 | maison | `don't go L5, go L3` | - | N | L3/N | oui |
| 22 | maison | `should we go L5 on this? no - go L3` | - | N | L3/N | oui |
| 23 | maison | `go L3 then do L4 later if needed` | - | N | L3/N | oui |
| 24 | maison | `go L4 or L5? what would it cost` | - | N | -/N | oui |
| 25 | maison | `run l2 cache flush` | - | - | -/L2 | oui |
| 26 | maison | `go level 3 of the building` | - | L3 | -/L3 | oui |
| 27 | maison | `go deeper on lane 3` | L1 | - | - | oui |
| 28 | maison | `Go Very Deep` | L2 | L2 | L2 | oui |
| 29 | maison | `ultra deep audit please` | L3 | L3 | L3 | oui |
| 30 | projet | `go L3 on this` | - | L3 | L3 | oui |
| 31 | projet | `go extremely deep` | L3 | L3 | L3 | oui |
| 32 | projet | `go very deep` | L2 | L2 | L2 | oui |
| 33 | projet | `go deep` | L1 | L1 | L1 | oui |
| 34 | projet | `lets go l4` | - | L4 | L4 | oui |
| 35 | projet | `do an L5 on the quote engine` | - | L5 | L5 | oui |
| 36 | projet | `go L4` | - | L4 | L4 | oui |
| 37 | projet | `go l5 on the stock module` | - | L5 | L5 | oui |
| 38 | projet | `go level 4 on the CRM screens` | - | L4 | L4 | oui |
| 39 | projet | `go level five` | - | L5 | L5 | oui |
| 40 | projet | `go L2 on the facture bug` | - | L2 | L2 | oui |
| 41 | projet | `go l1` | - | L1 | L1 | oui |
| 42 | projet | `go ship-grade on Taches` | - | L4 | L4 | oui |
| 43 | projet | `go all the way on calepinage` | - | L5 | L5 | oui |
| 44 | projet | `go beyond extremely deep` | L3 | L3 | L3/L5/N | oui |
| 45 | projet | `lance un L4 sur le module stock` | - | L4 | L4 | oui |
| 46 | projet | `fais un l3 sur les devis` | - | L3 | L3 | oui |
| 47 | projet | `go extremly deep please` | L3 | L3 | L3 | oui |
| 48 | projet | `deep dive into the payroll` | L1 | L1 | L1 | oui |
| 49 | projet | `go deeper on lane 3` | L1 | - | - | oui |
| 50 | projet | `la tâche L4-12 est bloquée` | - | - | - | oui |
| 51 | projet | `niveau l3 du stock` | - | - | - | oui |
| 52 | projet | `I care deeply about this` | - | - | - | oui |
| 53 | projet | `regarde le L5 du plan` | - | - | - | oui |
| 54 | projet | `le golang go lives here` | - | - | - | oui |
| 55 | projet | `Hugo L4 a écrit` | - | - | - | oui |
| 56 | projet | `go L4-12 again` | - | - | - | oui |
| 57 | projet | `voir PLAN L3 section 4` | - | - | - | oui |
| 58 | projet | `please read this` | - | - | - | oui |
| 59 | projet | `go L4 on stock` | - | L4 | L4 | oui |
| 60 | projet | `run the L2 cache test` | - | - | - | oui |
| 61 | projet | `please read this⏎go L4 on stock` | - | L4 | L4 | oui |
| 62 | projet | `ok⏎go deep` | L1 | L1 | L1 | oui |
| 63 | projet | `ok⏎go very deep` | L2 | L2 | L2 | oui |
| 64 | projet | `x⏎lets go l5` | - | L5 | L5 | oui |
| 65 | projet | `ago L4` | - | - | - | oui |
| 66 | projet | `run the 82-21 flag` | - | - | - | oui |
| 67 | projet | `nothing here` | - | - | - | oui |
| 68 | ajout | `let's go all the way down the list` | - | - | - | oui |
| 69 | ajout | `go lone wolf on this one` | - | - | - | oui |
| 70 | ajout | `relis ce que dit le rapport : « go L4 sur le stock »` | - | N | -/N | oui |
| 71 | ajout | `go L4 sur le stock, pas de question` | - | N | L4/N | oui |
| 72 | ajout | `go L5 on Taches` | - | L5 | L5 | oui |

**Résultat : 72 phrases, 72 conformes, 0 non conforme ; 0 déclenchement de L4 ou L5 à tort.** Durée par appel mesurée
pendant l'essai : 0,32 à 0,76 s (commande actuelle : ≈ 0,4 s sur 5 appels).

## Limites connues (assumées)
- Le crochet lit TOUTE l'entrée, comme l'actuel (lire le seul champ `prompt` demanderait `jq` ou Python). Un texte collé
  qui contient « go L4 » sans aucun signe d'ambiguïté déclenche encore le texte L4 ; ce texte dit d'ignorer une phrase
  trouvée seulement dans un texte collé ou cité, et la ligne de coût obligatoire précède tout tour.
- Le texte neutre est le côté sûr : il peut partir alors que Reda voulait vraiment L4 (« go L4 sur le stock, pas de
  question » → neutre) ; la skill lit alors sa phrase et lance L4, car un niveau qu'il nomme l'emporte toujours.
- Faux positifs bas coût, gardés : « go level 3 of the building » → L3. « niveau 4 », « en L4 », « go max » ne sont
  pas reconnus, exprès.
- La commande suppose Git Bash : `[\]n` y est une classe qui contient la barre oblique inverse (le retour à la ligne
  du message arrive dans le JSON sous la forme des deux caractères `\` `n`).
