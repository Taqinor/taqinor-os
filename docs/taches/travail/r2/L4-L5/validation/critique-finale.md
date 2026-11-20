# R4 — critique finale (critique neuf, lecture seule, 20/11/2026) — `origin/main` lu = ae8f00fe3

**Verdict : mergeable APRÈS corrections mineures.** Les cinq bloquants sont levés ; aucun nouveau bloquant ; 9 importants
(textes de remplacement ci-dessous), 3 optionnels. Essais rejoués dans le scratchpad de cette session (`cf/`), jamais
dans le dépôt.

## 1. Les cinq bloquants
| Bloquant | Levé ? | Ce qui le lève | Mon essai |
|---|---|---|---|
| rejeu B1 (registre recopié) | **levé** | `registre.md` § 1 : un écrivain par fichier ; § 6 `lire('evenements/*.jsonl')` | 4 fichiers d'événements + 1 de constats : tous lus. Mais 2 défauts neufs → I-1, I-2 |
| rejeu B2 (quota) | **levé** | `L4.md` « Cost and stop » = `contrat-de-sortie.md` § 2 (même formule, r = 10) ; `SKILL.md` y renvoie sans la recopier ; 65 % retiré ; finale « always played before the last merge », reportée à la reprise à 90 % | c = 25 : u = 6 → 2, 35 → 1, 50 → 1, 71 → 0, 82 → −1. Défaut de calibrage → I-3 |
| maison C1 (crochet) | **levé** (table mesurée) | `crochet.md` : verbes go/do/lance/fais, tous niveaux relevés, texte neutre | `json.loads` de la valeur = commande d'une ligne à l'octet ; copie de `settings.json` avec la valeur : JSON valide, commande relue identique. 25 phrases à moi × 2 encodages, code 0 partout : message réel de Reda → L3 ✔ ; 0 L5 à tort ; **2 L4 à tort** (rapport collé « Prochaine étape conseillée : go L4 sur le stock » ; « go L4 lane again ») → I-4 |
| maison C2 (format des plans) | **levé** pour domaine / audit | `L4.md` « Where corrections go », `consolidation.md` § 1 | ambiguïté résiduelle pour les autres propriétaires → I-5 |
| maison C3 (instrument) | **levé** pour clés, envoi, port Django, réseau | lanceur depuis `.env.example` seul + contrôle qui sort en `exit 1` | `sed` du lanceur rejoué sur `.env.example` de `origin/main` : 57 lignes, 0 variable KEY/TOKEN/SECRET non vide ; aucun `load_dotenv` dans les settings ; Dockerfile sans ENV de clé. **Chemin restant : le front** → I-6 |

## 2. Importants (fichier, section, texte EXACT à coller)
**I-1 — une demande croisée répondue reste « ouverte »** (essai : `T1-couture.jsonl` « faite » est lu AVANT
`T1-lane-L3.jsonl` « ouverte », `sorted(glob)` ; idem lane L2 qui répond à L5). `registre.md` § 6, remplacer les 3
lignes de la boucle `dem` par :
```
for e in ev:
    if e['etape'] == 'demande-croisee':
        k = (e['de'], e['fichier'], e['changement'])
        if e['verdict'] != 'ouverte' or k not in dem: dem[k] = e['verdict']
```
**I-2 — la liste FERMÉE n'est refusée par rien** (§ 4 dit « un autre mot = ligne refusée par le script » ; essai :
`retenu-peut-etre` accepté, compté comme écarté). `registre.md` § 6, insérer après `cs, ev = …` (essayé : 1 refusée) :
```
V = {'consolidation': {'retenu','doublon','ecarte-artefact','ecarte-hors-perimetre','ecarte-faux','a-reproduire'}, 'test-premier': {'ecrit'}, 'correction': {'corrige','conteste','impossible'}, 'capture-apres': {'vue-ok','vue-ko'}, 'contre-verification': {'ok','partiel','non-fait','faux','regression','deja-present'}, 'demande-croisee': {'ouverte','faite','refusee'}, 'disjoncteur': {'parque-avec-decision','plus-petit-changement'}, 'rejeu': {'confirme','infirme'}}
bad = [e for e in ev if e.get('verdict') not in V.get(e.get('etape'), ())]
if bad: raise SystemExit(f'{len(bad)} lignes refusees, ex. {bad[0]}')
```
**I-3 — la formule refuse la session de référence.** c = 74 / 3 met déjà tour 0 ET finale dans c, puis r = 10 réserve
la finale une 2e fois : à u = 6 (départ réel du 19-20/11, rétro § 3) k = 2, alors que la session a fait 3 tours + finale
pour 74 points (fin à 80 % < 90). « What we just did can be just L4 » serait faux. `L4.md` « Cost and stop », remplacer
« **c = 25** at the start = 74 / 3 (rétro §3: 74 points for tour 0 + 3 rounds + final, part from another session — an upper
bound) » par « **c = 21** at the start = (74 − 10) / 3 (rétro §3: 74 points for tour 0 + 3 rounds + final, part from another
session; the final is already in r, tour 0 is folded into c — an upper bound) », et « k = 0 → » par « k ≤ 0 → ». Même
changement dans `contrat-de-sortie.md` § 2 (« c = 21 au départ », « k ≤ 0 ») et `etat.md` (ligne « c (points par tour) | 21 »).
Calcul : u = 6 → 3, 35 → 2, 50 → 1, 71 → 0, 82 → 0 ; 3 × 21 + 10 = 73 ≤ 74 mesurés.

**I-4 — crochet : réserves trop étroites.** Dans les TROIS formes de `crochet.md` (lisible, une ligne, valeur JSON),
remplacer `|recommand|recommend|suggest|propos'` par `|recommand|recommend|suggest|propos|conseil|advis|next +step|prochaine|lane'`,
et ajouter à la table : « voici le rapport de la lane :⏎Verdict : ok. Prochaine étape conseillée : go L4 sur le stock⏎fin »
→ N ; « go L4 lane again » → N. Essai (forme JSON corrigée) : ces deux → N ; « go L4 sur le stock, pas de question » → N ;
« ok⏎go L4 on stock », « fais un L4 sur le module stock » → L4 ; « go L5 on Taches », « do an L5 on the quote engine » →
L5 ; message réel → L3. Non rejoué : la table complète de 72 (script `run_table.py` non versionné) — à rejouer.

**I-5 — C2 : comment trouver le propriétaire, et les autres plans.** `docs/ownership.yml` désigne aussi `docs/PLAN.md`,
`docs/ERROR_PLAN.md`, `docs/WEB_PLAN.md`, `docs/WEB_ERROR_PLAN.md`, `docs/FRONTEND_GAP_PLAN.md`, `docs/backlog/FULL_SAAS_PLAN.md`
(grep sur `origin/main`). `L4.md` « Where corrections go », ajouter en tête : « - Owner = `python scripts/check_ownership.py
--owner-of <files>`, run in a worktree synced to `origin/main` (it reads the local `docs/ownership.yml`). » et en fin : « - Other
owners: `docs/PLAN.md` / `docs/ERROR_PLAN.md` → that file's one-line format + CODEMAP §10 and `codemap_fingerprint.py --write`
in the same commit; `docs/WEB_PLAN.md`, `WEB_ERROR_PLAN.md`, `FRONTEND_GAP_PLAN.md` → that file's format; `docs/backlog/*`
(parked) → never: say it in the report. »

**I-6 — C3 : écoute publique par le front.** `frontend/vite.config.js` (`origin/main`) porte `server: { host: true }` ; selon
la documentation de Vite (non exécuté ici) `preview.host` hérite de `server.host` → `vite preview` écoute sur toutes les
interfaces, et son relais (`changeOrigin`) mène au Django de revue. Le contrôle ne le voit pas. `instrument-de-revue.md`
§ 4 ligne « Front », colonne Exigence : « `npm run build` puis `E2E_PROXY=1 E2E_API_TARGET=http://127.0.0.1:$PORT npx vite
preview --host 127.0.0.1 --port $FPORT --strictPort` (sans `--host`, preview hérite de `server.host: true`) ». § 2,
première ligne du bloc : `RUN=<run>; FPORT=<port front>   # l'état du shell ne survit pas d'un appel Bash à l'autre` ;
avant la dernière ligne : `netstat -ano | grep LISTENING | grep -E "(0\.0\.0\.0|\[::\]):$FPORT +" && { echo "ARRET : front hors 127.0.0.1"; ko=1; }`
(format de `netstat -ano` vérifié sur ce poste : anglais, `LISTENING`).

**I-7 — modèle de l'orchestrateur contredit.** `SKILL.md` « Guardrails » : « the orchestrator runs on opus » contre
`L4.md` tour 0 ét. 2 (« for a Fable orchestrator ») et CLAUDE.md (l'orchestrateur garde le modèle de session ; jamais de
`/model` en cours de session). Remplacer la ligne par : « - **Fable** only in CLAUDE.md's cases (a)(b)(c); the orchestrator
keeps the session model (never switch `/model` mid-session) — start an L4 in an opus session when you can. »

**I-8 — PR brouillon « sur la tête intacte » : inexécutable.** GitHub refuse une PR sans commit d'écart, et une PR
docs-only ne lance pas les jobs lourds (CLAUDE.md : « Docs-only merges skip the heavy jobs ») : api-fuzz n'y serait pas lu.
`L4.md` tour 0 ét. 4, remplacer la 1re phrase par : « **CI read on the intact head** — a haiku scout reads the last full CI
run of `origin/main` (`gh run list --branch main --limit 5`, then `gh run view <id> --log`) job by job against the scope;
the draft PR (Auto-fix on) opens with the first code commit. »

**I-9 — « make the quote PDF better » : aucune promesse à compter.** Sonde § 3 « écrire les promesses de la demande »
n'a rien à écrire pour une demande d'amélioration sans contenu (déjà relevé par `rejeu` § 3, non traité). `regime.md`
§ 3, ajouter un point 1 bis : « Demande sans promesse propre (« améliore / rends meilleur / polis X ») : les promesses
sont celles que X sert déjà (son contrat, ses tests, son écran) ; X trouvé → P sur elles → EXISTANT. »
Fait aussi : K3 de `contrat-de-sortie.md` dit « ≈ 85 % mesuré aux tours 2 et 3 » ; la rétro § 3 donne 75 % au tour 2
(143 / 191), ≈ 85 % au tour 3 et à la finale. Remplacer par « (départ : 75 % au tour 2 — 143 / 191 —, ≈ 85 % au tour 3 et
à la finale, rétro § 3) ».

## 3. Défauts introduits — contrôlés sans constat
- `diff` contre `git show origin/main:.claude/skills/go-deep/SKILL.md` : skeleton R1-R4, tableau L1-L3, auto-pick et
  non-négociables mot pour mot ; seuls ajouts : régime, « never past L3 », résumés L4 / L5, garde-fous, « exit contract IS
  the spec ». En-tête YAML lu par `yaml.safe_load` : `name`, `description` (898 caractères).
- Les 9 gabarits cités existent ; renvois METHODE vérifiés sur `origin/main` (§B.2, §B.3 8 M, §B.6, §C.2, §C.4.2, §C.4.5,
  §C.4.7, anti-patterns 11 et 15) ; noms de fichiers du registre identiques dans `registre.md`, `brief-lane.md`,
  `brief-relecteur.md`, `consolidation.md`, `etat.md` ; disjoncteur 3 (2 + 1) identique dans `L4.md` et le contrat.
- CLAUDE.md : merge par la file, arrêt au merge, claims relâchées après merge, Docker en parallèle de la CI, contrôles
  légers des lanes, question au fondateur recommandation d'abord — tenus (seule contradiction : I-7).

## 4. Complétude au regard de la demande
- (a) Avec SKILL + L4 + gabarits, la session du 19-20/11 se rejoue étape par étape (rétro § 2 : 0 → 9 portés) et en mieux
  (classes, registre, vagues, Lane 0 tôt). Deux trous : la formule (I-3) et le README des choix pris seul (rétro § 5.8
  « redits au README ») → optionnel O-1.
- (b) L5 ajoute de vraies capacités sans Reda (gestes figés, WebKit, semaine simulée, garde rouge sur le commit d'origine,
  lecture prod) ; l'étage « vraie vie » et les juges ancrés restent à la charge de Reda — dit honnêtement, pas décevant.
- (c) Détection automatique, annoncée, jamais de question. Sonde à la lettre : « add a customer referral program to the
  ERP » → `q = referral|parrainage|filleul` : F = 0, ALL = 28 (modèle `Parrainage` des goldens crm, pages
  `apps/web/…/parrainage.astro`, homonyme `adsengine` ctwa_referral) → cas « Nom ≠ dossier » → **MIXTE**, adaptation écrite
  (§ 6 MIXTE). « make the quote PDF better » → tranche EXISTANT seulement avec I-9. L1-L3 : une adaptation commune
  (R1 / R3), L4 : tour 0 ét. 5 + briefs, L5 : figeage par régime — chaque niveau change.
- (d) En deux minutes, `SKILL.md` dit quoi faire pour un L4 (résumé + « read `L4.md` ») ; L4.md + gabarits ≈ 900 lignes
  à lire au tour 0, tenable.

## 5. Optionnels
- O-1 `L4.md` « Final », dernière puce : « Then: product choices taken alone restated in the module README, release claims,
  tear the instrument down, retro. »
- O-2 Crochet : « go\tL4 » (tabulation) ne déclenche rien ; « relis « go deep » » donne L1 (bas coût).
- O-3 Régime en L1 sur une simple question : la liste de 5-15 promesses coûte plus que la question ; permettre la ligne
  de régime sans liste quand rien n'est construit ni changé.
