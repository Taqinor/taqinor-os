# Specs d'acceptation en direct (AMET90)

Une spec par **groupe d'audit** : `frontend/e2e/acceptation/<g>.spec.js` (`<g>` = groupe en
minuscules, ex. `adep.spec.js`). Jouée par l'ORCHESTRATEUR du plan-run sur la pile locale
(CLAUDE.md étape 3-bis, `docs/audits/METHODE.md` §C.4), jamais par une lane, jamais en CI :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\acceptation.ps1 ADEP [-Build] [-EtapesSupplementaires <json>] [-DryRun]
```

Le lanceur monte la pile (`scripts/pile_locale.ps1` : up, migrate, rebuild du front, `seed_demo`
si vide), joue la spec (projet Playwright `acceptation`, `E2E_ACCEPTATION=1`,
`E2E_BASE_URL=http://localhost`, connexion `demo_admin` par `auth.setup.js`), relit
l'enregistrement avec `python scripts/check_acceptation.py`, puis le commite avec ses captures
SEULEMENT si la spec ET la garde sont vertes (jamais de push).

Le projet `acceptation` n'existe que sous `E2E_ACCEPTATION=1` et le projet `chromium` ignore
`e2e/acceptation/` par motif : le shard par-merge, `e2e-full` et la matrice nocturne ne changent pas.

## Écrire une spec

```js
import { groupe } from './_oracles.js'
const etape = groupe('ADEP', ['ADEP16', 'ADEP19', 'ADEP99'])   // groupe porteur + `couvre`
etape('P5.4', ['ADEP19', 'ADEP99'], async ({ page, context, suivi }) => { … })
```

- **Une étape = un test** ; son id est celui du plan (`P<n>.<m>` du groupe, ou `PA<n>.<m>` d'un
  parcours) ; ses tâches = les ids que l'étape prouve (≥ 1). Chaque id de `couvre` a ≥ 1 étape.
- **Seulement des comportements présents sur l'arbre** : une étape qui affirme une tâche encore
  ouverte est rouge par construction — elle attend que la tâche soit construite.
- **Données propres** à l'étape, créées par l'API (`page.request`) et nettoyées à la fin ; jamais
  la prod, jamais une dépendance à une autre étape.
- **Clause de persistance** : recharger après l'action et revérifier (file, liste, écran).
- **Échecs injectés** (route Playwright, `context.setOffline`) : les déclarer AVANT avec
  `suivi.attendre(urlRegex, statut)` (`'reseau'` = échec réseau seul) — ce sont les SEULS 4xx/5xx
  et « Failed to load resource » excusés ; tout autre déclenche l'oracle.
- `suivi.surveiller(page)` pour chaque page ouverte en plus (deux onglets…) ;
  `suivi.verifie(5)` après avoir relu une liste juste après une création.
- Service worker bloqué dans ce projet (l'interception doit voir chaque requête de la page).

## Oracles 1-10 (numérotation de `.claude/skills/qa-explorer/SKILL.md` STEP 2)

| n° | Oracle | Dans la spec |
|---|---|---|
| 1 | réponse ≥ 500 même origine | observé sur chaque page (PASS sauf incident) |
| 2 | 4xx même origine sur une action légitime | observé (PASS sauf incident) |
| 3 | `console.error` / `pageerror` / rejet non géré | observé (PASS sauf incident) |
| 4 | dialogue natif (`alert`/`confirm`/`prompt`) | observé, refermé (PASS sauf incident) |
| 5 | liste vide juste après une création | `suivi.verifie(5)` quand l'étape relit la liste, sinon NA |
| 6 | PDF `/proposal` en échec | NA sauf étape devis qui le vérifie (`verifie(6)`) |
| 7 | `prix_achat` visible côté client | NA sauf étape sortie client (`verifie(7)`) |
| 8 | écran cassé (« Une erreur est survenue ») | relu sur chaque page en fin d'étape |
| 9 | donnée d'une autre société | NA sauf étape multi-société (`verifie(9)`) |
| 10 | cohérence documentaire (`audit_coherence`) | NA (commande de l'orchestrateur) |

Une étape est PASS si son corps passe ET aucun oracle n'est FAIL. Un FAIL est enregistré aussi
(il reste une trace, il ne couvre rien).

### Écart accepté

Une étape dont le corps passe mais qu'un oracle fait tomber sur un défaut ANTÉRIEUR, hors des
tâches qu'elle prouve, se déclare en 4ᵉ argument :
`etape('P1.13', ['ADEP40'], corps, { ecart: { base: 'FAIL', raison: '…' } })` — décision de
l'orchestrateur, jamais un réflexe. Effets : `base_verdict: FAIL` (l'étape échouait déjà à la
base, avant les tâches), ses tâches vont dans `couvre_avec_ecart` (et restent dans `couvre`), la
raison (le défaut, son fichier, pourquoi il est hors périmètre) ouvre les `notes`. Le test reste
vert si seuls les ORACLES échouent ; une assertion du corps qui échoue le fait toujours tomber.
L'enregistrement reste PASS — même règle que la garde : chaque étape PASS, ou FAIL avec
`base_verdict: FAIL` et toutes ses tâches dans `couvre_avec_ecart`. Le défaut est classé chez
son propriétaire (plan d'audit), l'écart disparaît quand il est corrigé.

## L'enregistrement (contrat AMET88 — docstring de `scripts/check_acceptation.py`)

`_enregistrement.js` écrit en `afterAll` :
`docs/audits/acceptation/<G>/<AAAA-MM-JJ>-<sha9>.results.json` (FAIT FOI : `sha`, `date`,
`groupe`, `verdict`, `couvre`, `couvre_avec_ecart`, `etapes[{id, taches, verdict, base_verdict,
trace, oracles{"1".."10"}, notes}]`) et le `.md` frère (en-tête YAML identique + tableau
lisible). `sha` = `git rev-parse HEAD` (ou `ACCEPTATION_SHA`), `date` = jour local,
`trace` = capture `docs/qa-explorer/captures/<date>/ACCEPTATION-<G>-<étape>.jpg` (la trace
Playwright complète reste dans le rapport). Verdict PASS seulement si toutes les étapes sont PASS.
Un rejeu le même jour au même sha COMPLÈTE l'enregistrement (étape de même id remplacée).

Étapes jouées hors navigateur (sondes, builds, gardes — ex. P1-P4 d'ADEP99) : fichier JSON
(liste d'étapes au format ci-dessus, ou `{couvre, etapes}`) fusionné par
`node e2e/acceptation/_enregistrement.js <G> --etapes-supplementaires <fichier.json>`
(ou `-EtapesSupplementaires` du lanceur) ; une étape incomplète est refusée.

## Exemple : `adep.spec.js`

| Étape | Tâches | Ce qui est joué (écran terrain « Ma journée », onglet Réserves) |
|---|---|---|
| P5.1 | ADEP16, ADEP17, ADEP99 | deux onglets hors ligne, une réserve dans chacun, retour du réseau → 2 réserves serveur, file vide |
| P5.2 | ADEP16, ADEP99 | l'appel en ligne applique puis expire → la file rejoue la MÊME clé (`replayed`) → 1 réserve |
| P5.3 | ADEP18, ACHT69, ADEP99 | lot refusé en 403 → chaque op marquée (badge : op_type — détail), persistée, abandonnée |
| P5.3-500 | ACHT69, ADEP99 | même chose en 500 |
| P5.4 | ADEP19, ADEP99 | `/auth/me/` sans réponse puis 503 → écran « Hors ligne » sur `/dashboard`, jamais `/login` ; réessayer → l'app |
