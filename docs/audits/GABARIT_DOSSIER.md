# GABARIT_DOSSIER — source unique du dossier d'audit v3 (METHODE §C.3)

Le lint `scripts/check_audit_dossier.py` (AMET, à construire) lit ICI l'ordre des `##`, les en-têtes de tableaux et les
règles ci-dessous ; METHODE §C.3 pointe dessus sans les recopier. Ne s'applique qu'aux fichiers portant le commentaire
`dossier-v3` (les 19 dossiers v2 restent un historique lecture seule). Premier exemple : `docs/audits/2026-10-09-methode.md`.

## Règles
1. **Ordre fixe** des 9 sections `##` ci-dessous ; commentaire d'en-tête complet ; `constats` / `taches` / `decisions` =
   lignes du §3 = tâches réelles du groupe (tous fichiers de plan) = registre.
2. **Taille** : lignes ≤ 400 caractères ; tout hors tableau §3 ≤ 12 Ko ; total ≤ 12 Ko + 400 o × constats.
3. **Tableau §3** : chaque `C-<G>-NNN` cité par une tâche du groupe existe en §3 ; chaque ligne a ≥ 1 tâche ou va en §7 ;
   « Sonde » = chemin EXISTANT `docs/audits/sondes/<G>/C-<G>-NNN.py` ou `STATIQUE` ; STATIQUE interdit en S1-S2 sur les
   critères à sonde obligatoire (METHODE §A.4) ; ancre `fichier::symbole`, jamais `fichier:ligne`.
4. **Interdits** (regex) : ids de lane `\b[LV][A-Z0-9]{2,}-\d+\b`, `\bW\d+(-\d+)?\b`, « FABLE § », « lot W », chemins de
   scratchpad, « Voir l'en-tête du groupe », lignes de tâche `^- \[`, blocs de code > 5 lignes (les sondes vont dans
   `sondes/`), adresse e-mail, numéro de téléphone. Le nom court d'une lane n'est permis qu'en 1re colonne du §2.
5. **Décisions** : chaque D-id du §6 existe dans `docs/audits/decisions.yml` ; aucune tâche du groupe ne contient « Si (a) ».
6. **Coût** : la ligne §9 suit `H\d+ S\d+ O\d+ F\d+ · jetons sous-agents ≈ [\d,]+ M`.

## Squelette
```markdown
# Audit <ID ou PA> « <mot> » — <AAAA-MM-JJ> — L<n>
<!-- dossier-v3 | groupe: <PREFIXE> | base: <sha7> | fraicheur: <sha7> | constats: <n> | taches: <n> | decisions: <n> -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | possédé `<globs>` ; lu `<globs>` (registre / parcours <PA>) |
| Niveau | L<n> — <raison, une ligne> |
| Données | demo ; anon : <chargé | non requis : raison> ; prod lecture seule : <mesures | aucune> |
| Critères retenus | C<n>, … |
| Étapes | P1.1 <libellé> · P1.2 … (parcours : <PA>.<n>) |
| NE PAS REFAIRE | <ids ouverts ou cochés qui couvrent déjà le terrain> |
| Non-objectifs | … |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
Détecteurs : `<commande>` → <verdict> @<sha7> · non exécutés : <nom> (raison).
Live : <scénarios joués> · prévus non joués : <…> · prod : <mesure → valeur agrégée>.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
Porte : <r> réfutés / <n> bruts · seconde lentille : <k> S1 → maintenus <a>, gravité revue <b>, élargis <c>.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|

## 7. Optionnel (jamais une tâche)
- <libellé> — <une ligne>

## 8. Limites, non couvert, écarts
- Non couvert : …
- Écart à la méthode : <écart> → <amendé METHODE §x dans cette PR | ponctuel : raison>
- Incident prod : <aucun | INCIDENT PROD … → <G>n P0>

## 9. Coût et routage
Coût : H<n> S<n> O<n> F<n> · jetons sous-agents ≈ <x,y> M · tâches <n> (M0 <a> M1 <b> M2 <c> M3 <d> GATED <e>).
Routage : `PLAN_AUDIT_<A>.md` <n> · `PLAN_AUDIT_<B>.md` <n> · acceptation <G><n> · PR #<n>.
```
