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
| `manage.py qa_export_anonymise` / `qa_import_anonymise` (`authentication/anonymise.py`) | Jeu de données réaliste anonymisé (`dataset: anon`) — voir « Données réalistes anonymisées ». |
| `manage.py audit_coherence` | Oracle dur n°10 : contrôles de cohérence déterministes des documents, lancés par l'orchestrateur après les missions ventes et crm (ignoré tant que la commande n'existe pas). |

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

## Données réalistes anonymisées (`dataset: anon`)

`seed_demo` ne contient que 5 devis nus et 3 leads réduits à un nom : les branches
où vivent les vrais bugs (factures d'électricité, distributeurs, études, options,
pompage, C&I) n'y sont jamais exercées. On peut donc donner à l'explorateur une
**copie anonymisée de la prod** : identités brouillées ; montants, profils
énergie, études, lignes, statuts gardés. Tant qu'aucun instantané n'existe,
`dataset: demo` (le défaut) ne change rien.

**1. Produire l'instantané sur le serveur (lecture seule).** La commande lit dans
une transaction annulée (déclarée `READ ONLY` sous PostgreSQL) et n'écrit rien en
base ; elle refuse d'écrire le fichier dans le code source.

```bash
ssh -i ~/.ssh/taqinor_hetzner root@178.105.192.116
cd /opt/taqinor-os
# slug de la société (une fois) :
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core \
  python manage.py shell -c "from authentication.models import Company; print(list(Company.objects.values_list('slug', flat=True)))"
mkdir -p /root/taqinor-anon && chmod 700 /root/taqinor-anon
C="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
$C exec -T django_core python manage.py qa_export_anonymise --company <slug> --out /tmp/latest.anon.json.gz
# options : --since 2026-01-01 (documents créés depuis) --limit 300 (N plus récents par type)
$C cp django_core:/tmp/latest.anon.json.gz /root/taqinor-anon/latest.anon.json.gz
$C exec -T django_core rm -f /tmp/latest.anon.json.gz
```

(`/tmp` du conteneur : hors du code monté dans `/app`, que la commande refuse.
`--out -` écrit sur stdout, mais un message de journalisation au démarrage
corromprait le fichier — préférer `/tmp` + `cp`.)

**2. Le rapatrier puis l'effacer du serveur** (depuis la racine du dépôt, en
local) :

```bash
mkdir -p var/anon
scp -i ~/.ssh/taqinor_hetzner root@178.105.192.116:/root/taqinor-anon/latest.anon.json.gz var/anon/latest.anon.json.gz
ssh -i ~/.ssh/taqinor_hetzner root@178.105.192.116 rm -f /root/taqinor-anon/latest.anon.json.gz
```

**3. L'importer** — automatique : avec `dataset: anon` dans
`docs/qa-explorer.config.yml`, la passe importe l'instantané s'il est plus récent
que le dernier import. À la main (stack locale, `DJANGO_DEBUG=True`) :

```bash
docker compose cp var/anon/latest.anon.json.gz django_core:/tmp/latest.anon.json.gz
docker compose exec -T django_core python manage.py qa_import_anonymise --in /tmp/latest.anon.json.gz
docker compose exec -T django_core rm -f /tmp/latest.anon.json.gz
```

`qa_import_anonymise` refuse hors `DEBUG`, ne touche **que** la société
`taqinor-anon` (vidée puis rechargée à chaque import — idempotent), remappe toutes
les clés, et crée le compte `anon_admin` (mot de passe dans le fichier de la
commande, local seulement). Il insère les lignes sans `save()` ni signal : aucune
notification, aucun e-mail, aucun webhook, aucun chatter, aucun `devis_accepted`.

**Ce qui est gardé / brouillé / supprimé** (politique complète :
`backend/django_core/authentication/anonymise.py`) :

| Gardé tel quel | Brouillé (faux stable par valeur) | Supprimé |
| --- | --- | --- |
| nombres (montants, `prix_achat`, kWc, factures hiver/été, conso…), booléens, dates, statuts et toutes les énumérations (distributeur, type d'installation…), références de documents, désignations de lignes, fiche catalogue (nom, marque, description, garantie, `courbe_pompe`), ville, tranche ONEE | noms, prénoms, sociétés, e-mails, téléphones/WhatsApp, adresses, CIN/ICE/RC/IF/RIB, notes et tout texte libre ; dans les JSON (études, questionnaires) : clés d'identité, e-mails, téléphones, textes longs | fichiers, photos, signatures, jetons (portail, liens publics), UUID, chemins PDF, coordonnées précises du toit ; GPS arrondi à 0,1° (~11 km) ; tous les utilisateurs remplacés par `anon_admin` ; chatter non exporté |

**Fail-closed** : un champ texte que personne n'a classé (ajouté demain) est
brouillé par défaut, un type de champ inconnu est vidé (test
`authentication/tests/test_anonymise.py`). Le brouillage est déterministe au sein
d'un export (même nom → même faux : le dédoublonnage survit) avec un sel aléatoire
jamais écrit — deux exports ne se recoupent pas.

**Confidentialité — non négociable.** L'instantané contient de vrais montants et
de vrais prix d'achat : il ne vit que dans `var/anon/` (ignoré par git, comme tout
`*.anon.json.gz` ; la garde CI `scripts/check_no_anon_snapshot.py` refuse un
`git add -f`), n'est **jamais commité, jamais envoyé ailleurs** (ni e-mail, ni
cloud, ni ticket), et on **supprime les anciens instantanés** (on n'en garde qu'un,
`latest`). En jeu `anon`, la passe ne commite aucune capture d'écran et ses lignes
`ERR-QAH-*` ne citent aucun montant absolu, seulement la règle, la référence et
l'écart.

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
| 2026-09-28 | crm, visites, calepinage, ventes, stock, chantiers, sav, ged, portail, parametres (12 explorateurs sonnet, passes « en profondeur » ; portail côté client et SAV tickets/équipements non atteignables sur la démo) | 16 (4 Critical, 1 High, 9 Medium, 2 Low) — ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION … ERR-QAH-GED-UPLOAD-TXT-SILENT-REJECT | 3 (1 non reproduit, 2 à regarder par un humain) | ≈3,2 M tokens sous-agents (12 explorateurs sonnet ≈2,64 M + 2 rejoueurs opus ≈0,52 M + 1 éclaireur) + orchestrateur Fable ; ~3 h de mur |
| 2026-09-29 | crm, visites, calepinage, ventes, stock, chantiers, sav, ged, portail, parametres (10 explorateurs sonnet, 1 par module ; les 16 constats du 28/09 tous corrigés — non re-trouvés ; portail côté client non atteignable sans lien magique, calepinage : dessin toit bloqué par clé MapTiler absente = ENV) | 3 (1 High ERR-QAH-CHANTIERS-DATE-REALISEE-COMPTE-RENDU, 1 Medium ERR-QAH-VENTES-FORM-TOTAL-CEIL, 1 Low ERR-QAH-SAV-WORKSHEET-PROBE-404) | 5 (2 par-design/hors-oracle, 1 doublon d'affichage, 1 faux-positif visuel, 1 à regarder par un humain) | ≈1,3 M tokens sous-agents (10 explorateurs sonnet + 1 rejoueur opus) ; orchestrateur Opus ; vérifs racine via code+DB directes |
