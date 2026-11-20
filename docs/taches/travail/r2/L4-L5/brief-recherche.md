# Brief commun des lanes de recherche — concevoir les niveaux L4 et L5 de la skill `go-deep`

## Pourquoi
TAQINOR OS (ERP solaire, Django + React) est construit par un fondateur non-codeur, Reda, avec Claude Code : un
orchestrateur qui délègue à des sous-agents. La maison a déjà trois niveaux de profondeur (`go deep` L1, `go very deep`
L2, `go extremely deep` L3 : `.claude/skills/go-deep/SKILL.md` — LIS-LE). Les 19-20/11/2026, une session a fait bien
plus qu'un L3 sur un module livré : trois tours de relecteurs neufs sur l'écran RÉEL, ≈ 210 corrections, contre-
vérifiées, jusqu'au merge. Tout est raconté dans `docs/taches/travail/r2/RETRO-METHODE.md` — LIS-LE EN ENTIER, c'est le
point de départ. Reda demande d'en faire un niveau **L4** (ce qu'on vient de faire, rendu reproductible) et un niveau
**L5** « much more powerful », qui **détectent tout seuls si on construit du neuf ou si on améliore l'existant** et
s'adaptent. Ta lane cherche, dans SON domaine, comment font les meilleurs et ce que ça change pour L4 et L5.

## Règles
- Lecture et recherche seulement. Ta seule écriture : ton rapport
  `C:\dev\taqinor-os\.claude\worktrees\erp-task-manager-ai-f8db1b\docs\taches\travail\r2\L4-L5\recherche\<ton nom>.md`
  (crée-le tôt, écris au fil de l'eau ; par Bash si l'outil Write refuse).
- **Budget dur : 20 recherches web au plus** (plafond partagé entre toutes les lanes). Préfère lire en entier les
  sources premières avec WebFetch (documentation officielle, billets d'ingénierie, articles, dépôts) plutôt que
  multiplier les recherches. Si une page refuse, passe à une autre source, ne t'acharne pas.
- **Zéro fait inventé** (règle absolue de la maison) : chaque affirmation porte sa source (URL) et tu dis si tu l'as LUE
  dans la page cette session (« lu ») ou si tu la tiens de mémoire (« de mémoire, à vérifier »). Un chiffre sans source
  lue n'entre pas dans le rapport. Date ou version de la source quand elle est connue. Nous sommes le 20/11/2026 : dis
  quand une source est ancienne et peut être dépassée.
- Calibrage : on ne veut pas un panorama. On veut ce qui CHANGE la conception : une pratique à adopter, un piège à
  éviter, un critère chiffré, un mécanisme concret (fichier, boucle, rôle, garde), avec ce que ça coûte.

## Forme du rapport (français simple, 150 lignes au plus)
1. **L'essentiel en dix lignes** : ce que ta lane apprend à L4 / L5.
2. **Pratiques à adopter** (tableau) : pratique · qui la décrit (source, lu / mémoire) · le mécanisme précis · ce
   qu'elle aurait changé dans la session du 19-20/11 (cite le § de la rétro) · coût · niveau visé (L4, L5, les deux).
3. **Pièges et contre-indications** : ce que des sources sérieuses disent de NE PAS faire, ou qui contredit notre
   méthode (dis-le sans ménagement : une contradiction argumentée vaut plus qu'un accord).
4. **Neuf ou existant** : tout ce que ta lane a vu sur la façon d'adapter la méthode selon qu'on construit ou qu'on
   améliore, et sur la façon de le détecter.
5. **Critères de sortie et mesures** : comment les sources décident que c'est « assez bon » / « fini ».
6. **Non couvert, non trouvé, douteux.**
Ton message final : l'essentiel (1) + les trois pratiques les plus fortes + la contradiction la plus sérieuse, en
15 lignes au plus.
