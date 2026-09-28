# QA-Explorer — guide d'exploitation (QAH1)

Une flotte d'agents « testeur humain » qui, chaque nuit, **utilise l'ERP démo
comme un vrai utilisateur**, module par module, et dépose ce qui casse dans
[`docs/ERROR_PLAN.md`](ERROR_PLAN.md) sous forme de lignes `ERR-QAH-<MODULE>-<SLUG>`.
Corriger ces lignes reste le travail de `work on error plan` — l'explorateur ne
touche jamais au code.

**Le principe qui gouverne tout (recherche L2 du 27/09/2026, GROUPE QAH de
`docs/PLAN.md`) : un agent LLM explore bien et juge mal.** Donc l'agent
*explore*, et ce sont des **oracles durs** — sans aucun jugement d'IA — qui
décident qu'il y a un défaut : une réponse serveur 4xx/5xx, une erreur console,
une liste vide juste après une création, un PDF `/proposal` qui échoue, un
`prix_achat` visible côté client, des données d'une autre société à l'écran. L'IA
ne juge que les écrans ambigus, contre une grille écrite par module (totaux au
centime, chaîne d'états devis → BC → facture, référence unique…), jamais un vague
« est-ce que ça a l'air bien ».

## Les pièces (toutes versionnées)

| Fichier | Rôle |
| --- | --- |
| `.claude/skills/qa-explorer/SKILL.md` | Le cerveau : pré-contrôles + kill switch → exploration (un sous-agent sonnet par module) → rejeu indépendant → dédoublonnage → dépôt dans ERROR_PLAN → self-merge docs-only. |
| `docs/qa-explorer.config.yml` | Réglages + **kill switch** (`enabled`), modules, budget `max_minutes`, `max_agents`, contre-vérification optionnelle. |
| `.mcp.json` | Déclare les deux serveurs navigateur : **Playwright MCP** (`@playwright/mcp@0.0.82`) et **Chrome DevTools MCP** (`chrome-devtools-mcp@1.10.1`), versions épinglées, licence Apache-2.0, gratuits. L'entrée `serena` existante est inchangée. |
| `scripts/setup-nightly-qa.ps1`, `scripts/nightly-qa.ps1`, `docs/nightly-qa.md` | La nuit locale à 23:00 (QAH11) : préparation de la machine et lanceur quotidien. |
| `docs/qa-explorer/captures/<date>/` | Captures d'écran des constats déposés (JPEG, une par constat). |

## Comment une passe se déroule

1. **Pré-contrôles** : lecture du kill switch (arrêt immédiat si `enabled: false`),
   refus si l'URL cible n'est pas `localhost`, arrêt si une passe précédente tourne
   encore (marqueur `logs/nightly-qa/qa-explorer.running`) ou si le verrou
   single-writer de `scripts/test-backend.ps1` est tenu (un conteneur
   `erp-agentique-django_core-run*` actif), vérification que la stack répond et que
   la société démo est seedée (`seed_demo`, **jamais `--force`**).
2. **Exploration** : un sous-agent **sonnet** par module, avec un PERSONA et une
   MISSION en français courant (tableau ci-dessous). Il pilote le navigateur par
   Playwright MCP (arbre d'accessibilité, sans vision), relève réseau et console à
   chaque écran, et rapporte des *candidats* avec leurs preuves.
3. **Rejeu indépendant** : l'orchestrateur rejoue chaque candidat dans un **autre
   navigateur, propre** (Chrome DevTools MCP) — un constat n'est déposé que s'il se
   reproduit. C'est la parade à l'agent qui accuse son propre clic, et à celui qui
   contourne le bug pour « finir » sa mission.
4. **Contre-vérification (option `cross_check: true`)** : un agent opus à contexte
   neuf re-juge les constats « de grille » à partir des seules preuves (motif
   Passmark de Bug0).
5. **Dépôt** : une ligne par constat confirmé dans `docs/ERROR_PLAN.md` (titre,
   repro pas à pas, capture, sévérité, confiance, `Files:`), dédoublonnée contre les
   ERR existants, une ligne au journal d'intake, une ligne au tableau « Passes »
   ci-dessous, puis un seul PR docs-only auto-mergé (même flux que l'error-autopilot,
   CODEMAP §10 + `codemap_fingerprint.py --write` inclus). Aucune correction de code,
   aucun déploiement.

## Modules, personas et routes d'entrée (vérifiées dans `frontend/src` le 28/09/2026)

| Module | Persona | Routes d'entrée |
| --- | --- | --- |
| crm | commercial pressé | `/crm/cockpit`, `/crm/leads`, `/crm/leads/:id`, `/crm/relances` |
| visites | technicien sur mobile | `/visites`, `/visites/planifier`, `/visites/toutes`, `/visites/:id` |
| calepinage | technicien bureau d'études | `/calepinage`, `/calepinage/nouveau`, `/calepinage/:id/plan`, `/calepinage/:id/production` |
| ventes | comptable méfiante | `/ventes/devis/nouveau`, `/ventes/devis`, `/ventes/bons-commande`, `/ventes/factures`, `/ventes/avoirs` |
| stock | magasinier | `/stock`, `/stock/mouvements`, `/stock/categories` |
| chantiers (dossier `installations`) | chef de chantier sur mobile | `/chantiers`, `/interventions`, `/planification`, `/ma-journee` |
| après-vente (`sav`) | technicien SAV | `/sav/cockpit`, `/sav`, `/equipements`, `/sav/contrats` |
| ged | assistante administrative | `/ged` |
| portail client | client final, puis administrateur | `/portail/administration` ; côté client `/portail/client`, `/portail/client/devis`, `/portail/client/factures` |
| paramètres | administrateur prudent | `/parametres`, `/parametres/notifications`, `/parametres/messages-accueil`, `/parametres/historique-statut` |

Sources : `frontend/src/features/<module>/module.config.jsx` (routes des modules) et
`frontend/src/router/index.jsx` (`/ged`, portail client). Le portail client exige un
compte de portée `portail_client` : **aucun n'est seedé**, l'explorateur n'en invente
jamais ; s'il ne peut pas en créer un sur la stack locale sans rien envoyer vers
l'extérieur, il couvre le côté administration et signale le côté client comme
« non couvert ».

**Connexion** : `demo_admin`, compte créé par
`backend/django_core/authentication/management/commands/seed_demo.py` (mot de passe
défini dans ce fichier, le même que `ADMIN` dans `frontend/e2e/helpers.js`). La
seconde société démo (`taqinor-demo-full`, `seed_demo_company`) sert de témoin
d'isolation : ses noms de clients ne doivent JAMAIS apparaître sous `demo_admin`.

## Les serveurs navigateur (`.mcp.json`)

- **Approbation** : en session interactive, Claude Code demande d'approuver les
  serveurs d'un `.mcp.json` de projet — tapez `/mcp` et approuvez `playwright` et
  `chrome-devtools` une fois. En mode headless (`claude -p`, la nuit), Claude Code
  les charge sans demander. Pour les couper dans une session : réglage
  `disabledMcpjsonServers`.
- **Prérequis** : Node ≥ 20.19 (exigé par `chrome-devtools-mcp`) et Google Chrome
  installé (les deux serveurs pilotent Chrome). Le premier lancement télécharge les
  paquets via `npx` (versions épinglées — pour monter de version, changer le numéro
  dans `.mcp.json` après `npm view <paquet> version`).
- **Confidentialité** : `chrome-devtools-mcp` envoie par défaut des statistiques
  d'usage à Google et des URL de trace à l'API CrUX ; les deux sont coupés
  (`--no-usage-statistics`, `--no-performance-crux`). Les deux navigateurs tournent
  `--headless --isolated` (profil en mémoire, rien sur disque).
- **Windows** : si `/mcp` montre un serveur en échec au démarrage (`npx`
  introuvable), remplacer localement `"command": "npx"` par `"command": "cmd"` et
  préfixer les arguments par `"/c", "npx"` — à ne pas committer si l'autre machine
  fonctionne sans.

### Parallélisme (`max_agents`)

Tous les sous-agents d'une session partagent **le même** serveur Playwright, donc
le même navigateur et le même « onglet courant » : deux explorateurs simultanés se
voleraient la page. D'où `max_agents: 1` (les modules passent l'un après l'autre ;
la nuit, le temps n'est pas la ressource rare). Pour paralléliser : ajouter dans
`.mcp.json` un serveur Playwright isolé par explorateur supplémentaire
(`playwright-2`, `playwright-3`… mêmes arguments, `--isolated` obligatoire), puis
monter `max_agents` au nombre de serveurs et donner à chaque explorateur simultané
son propre serveur dans son brief.

## Le lancer

- **Chaque nuit à 23:00** (heure locale) : la tâche planifiée Windows
  `TAQINOR nightly QA`, créée par `powershell -File scripts/setup-nightly-qa.ps1`
  (voir [`docs/nightly-qa.md`](nightly-qa.md)).
- **À la main** : dans une session Claude Code ouverte à la racine du dépôt, stack
  démarrée : « run the qa-explorer skill ».

## L'arrêter

Deux interrupteurs — **un seul suffit** :

1. `enabled: false` dans `docs/qa-explorer.config.yml` : le lanceur de nuit sort sans
   rien tirer ni construire, et le skill imprime `QA_EXPLORER: DISABLED` sans rien
   changer.
2. La tâche Windows : `schtasks /Change /TN "TAQINOR nightly QA" /DISABLE`.

## Sécurité

- **Jamais contre la prod** : la cible est `http://localhost` ; toute autre URL est
  refusée.
- **Jamais `seed_demo --force`** ; jamais d'autre voie PDF devis que `/proposal`
  (règle #4 — l'explorateur ne fait que la LIRE) ; jamais d'e-mail/WhatsApp/SMS vers
  une vraie personne, jamais de campagne Meta, jamais de scraper, aucun lien externe
  suivi.
- `prix_achat` jamais dans une sortie client : l'explorateur le **signale** s'il le
  voit (constat Critique).
- Le skill n'écrit que `docs/ERROR_PLAN.md`, CODEMAP §10 (+ empreinte du plan), ce
  fichier (tableau des passes), les captures, et ses fichiers de marqueur/journal
  sous `logs/` (ignoré par git). Le merge docs-only passe par les quatre contrôles
  CI requis, sans approbation, jamais de force-push.
- Coût : la passe consomme l'abonnement Claude (aucune clé API — le lanceur retire
  `ANTHROPIC_API_KEY` de son environnement). Le journal de nuit contient
  l'estimation `total_cost_usd` du run.

## Passes

Une ligne par passe réelle qui a déposé au moins un constat (et la toute première
passe, même vide). Les passes sans constat ne laissent de trace que dans
`logs/nightly-qa/`.

| Date | Modules couverts | Constats déposés | Écartés (non reproduits / déjà connus) | Coût (tokens / estimation) |
| --- | --- | --- | --- | --- |
| _en attente — première passe réelle_ | _à remplir par la première passe nocturne (QAH11) : aucune passe réelle n'a encore tourné — le skill a été livré sans stack docker ni serveurs MCP approuvés_ | — | — | — |
