# QA de nuit — « setup nightly QA » (QAH11)

La passe `qa-explorer` (QAH1, [`docs/qa-explorer.md`](qa-explorer.md)) tourne **la
nuit, sur votre machine**, par une tâche planifiée Windows. Une seule commande la
met en place ; la même commande, tapée sur l'autre ordinateur, l'y configure à
l'identique. Elle ne décide rien : elle configure la machine où on la tape.

Pourquoi la nuit (23:00, heure de Casablanca, par défaut) : la passe partage la
fenêtre d'usage Claude, le CPU/RAM (12 conteneurs + Chromium) et le verrou
single-writer du test DB avec vos sessions de jour — la nuit, rien de tout cela
n'est en concurrence. Les nightly GitHub (`release-verify` 03:00 UTC, `mutation`
03:30 UTC) tournent sur les runners GitHub, pas sur vos machines : cette commande
n'y touche jamais.

## Prérequis

| Quoi | Pourquoi | Vérifié par |
| --- | --- | --- |
| Docker Desktop démarré (idéalement « au démarrage de Windows ») | la stack locale (12 conteneurs) | `docker info`, `docker compose version` |
| Node.js ≥ 20.19 | `npx` lance les deux serveurs MCP ; `chrome-devtools-mcp` exige 20.19+ | `node --version` |
| git | tirer `main` chaque nuit | `git` dans le PATH |
| Claude Code installé **et connecté** (abonnement Claude, pas de clé API) | la passe tourne en `claude -p` | `claude auth status` |
| Google Chrome | Playwright MCP et Chrome DevTools MCP pilotent Chrome | registre / dossiers d'installation |

Un prérequis manquant = une ligne d'action claire, puis la commande s'arrête sans
rien configurer. **Elle n'installe jamais rien en silence.**

## La commande

Dans PowerShell, à la racine du dépôt (sur `main`, sans modification en cours) :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-nightly-qa.ps1
```

Options :

- `-Time 01:30` — autre heure (heure LOCALE de la machine). 08:00 est possible mais
  déconseillé (concurrence avec vos sessions de jour).
- `-WithErrorAutopilot` — enregistre aussi la tâche `TAQINOR error-autopilot`
  (12:00 par défaut, `-ErrorAutopilotTime 13:00` pour changer) sur CETTE machine,
  pour décharger l'autre. Attention : à midi, son `docker compose up -d --build`
  peut redémarrer la stack locale pendant que vous travaillez.

Ce qu'elle fait, dans l'ordre : prérequis → dépôt sur `main` propre et à jour
(`git pull --ff-only` ; elle ne change jamais de branche à votre place) → `.env`
créé depuis `.env.example` s'il manque (et refus si `DJANGO_DEBUG` n'est pas `True` :
`seed_demo` l'exige en local) → `docker compose up -d --build` → attente de la
stack sur `http://localhost` → migrations → `seed_demo` si la société démo est vide
(**jamais `--force`**) → rappel `/mcp` → tâche planifiée. Elle finit par cinq lignes :
vérifié / créé / encore manuel / comment vérifier / comment couper.

**Relancer la commande met la tâche à jour, ne la duplique jamais**
(`schtasks /Create … /F` = créer ou remplacer la tâche du même nom).

### Une étape reste manuelle : approuver les serveurs MCP

Ouvrir `claude` à la racine du dépôt, taper `/mcp`, approuver **`playwright`** et
**`chrome-devtools`** (déclarés dans `.mcp.json`). La nuit, `claude -p` les charge
sans demander ; l'approbation sert aux passes lancées à la main.

## Ce que fait la tâche chaque nuit (`scripts/nightly-qa.ps1`)

1. **Lit le kill switch `docs/qa-explorer.config.yml` en premier** : `enabled: false`
   → sortie propre, rien tiré, rien construit, rien lancé.
2. Refuse de démarrer si une passe précédente tourne encore (verrou
   `logs/nightly-qa/nightly-qa.lock` portant le PID).
3. `git pull --ff-only origin main` — seulement si le dépôt est sur `main` sans
   modification suivie ; sinon refus, rien n'est touché.
4. Relit le kill switch après le pull ; « skill pas encore créé » (fichier absent)
   = sortie propre.
5. Démarre Docker Desktop s'il dort, `docker compose up -d --build`, attend la
   stack, applique les migrations, `seed_demo` si la société démo est vide.
6. Refuse si le verrou single-writer de `scripts/test-backend.ps1` est tenu (un
   conteneur `erp-agentique-django_core-run*` actif).
7. Lance `claude -p "run the qa-explorer skill (.claude/skills/qa-explorer/SKILL.md)"`
   en headless sur l'abonnement Claude — `ANTHROPIC_API_KEY` est retirée de
   l'environnement de la passe, l'orchestrateur tourne en `--model opus`, les
   sous-agents gardent les tags de modèle imposés par le skill (sonnet pour les
   explorateurs), `--permission-mode dontAsk` + une liste d'outils autorisés (tout
   le reste est refusé : personne ne répond aux demandes la nuit), chien de garde à
   `max_minutes + 30` minutes.
8. Le skill dépose ses constats `ERR-QAH-*` dans `docs/ERROR_PLAN.md` et fait un
   self-merge docs-only, comme l'error-autopilot. Aucun déploiement.

Codes de sortie (colonne « Last Result » de la tâche) :

| Code | Sens |
| --- | --- |
| 0 | passe terminée, ou sortie propre voulue (kill switch off, skill absent) |
| 1 | échec (git, docker, migrations, seed, passe claude en erreur, chien de garde) |
| 2 | refus de démarrer (passe précédente en cours, verrou test-backend tenu, dépôt pas sur un `main` propre) |

## Vérifier qu'elle a tourné

```powershell
schtasks /Query /TN "TAQINOR nightly QA" /V /FO LIST
```

Regarder `Last Run Time` et `Last Result` (0 = OK, voir le tableau ci-dessus).

## Lire le journal

`logs\nightly-qa\` (ignoré par git via `logs/`) :

- `qa-explorer-AAAAMMJJ-HHMMSS.log` — le déroulé horodaté de la nuit (git, docker,
  migrations, lignes de statut `QA_EXPLORER: …` / `ERROR_PLAN_STATUS: …`, coût
  estimé `total_cost_usd`) ;
- `qa-explorer-AAAAMMJJ-HHMMSS.json` — la sortie JSON complète de `claude -p` (le
  rapport de la passe dans le champ `result`) ;
- `qa-explorer-AAAAMMJJ-HHMMSS.stderr.txt` — les erreurs brutes de `claude`.

Les constats déposés arrivent dans `docs/ERROR_PLAN.md` (lignes `ERR-QAH-…`) par un
PR docs-only auto-mergé ; « work on error plan » les draine ensuite.

## La désactiver

Au choix — un seul suffit :

- la tâche : `schtasks /Change /TN "TAQINOR nightly QA" /DISABLE`
  (réactiver : `/ENABLE`) ;
- le kill switch : `enabled: false` dans `docs/qa-explorer.config.yml` (committé,
  il coupe la passe sur toutes les machines).

Supprimer complètement la tâche : `schtasks /Delete /TN "TAQINOR nightly QA" /F`.

## Changer l'heure

Relancer la commande avec la nouvelle heure — la tâche est mise à jour, pas
dupliquée :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-nightly-qa.ps1 -Time 01:30
```

(`schedule_note` dans `docs/qa-explorer.config.yml` n'est qu'un mémo : le modifier
ne change pas l'heure.)

## Bon à savoir

- Le PC doit être **allumé, session ouverte**, à l'heure de la passe (veille = pas
  de passe ; une passe manquée n'est pas rattrapée le matin, pour ne pas gêner vos
  sessions de jour). La commande autorise le démarrage sur batterie.
- La passe consomme l'abonnement Claude de la machine ; son coût estimé est dans le
  journal.
- Jamais contre la prod : la seule cible est `http://localhost`.
