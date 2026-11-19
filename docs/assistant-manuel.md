# Manuel de l'assistant IA — génération (AIC50)

L'assistant de l'ERP (agent `backend/fastapi_ia`) lit deux fichiers dans son prompt système (AIC5) :

- `backend/fastapi_ia/assistant/manuel.md` — « comment on fait X dans TAQINOR », par rôle ;
- `backend/fastapi_ia/assistant/capacites.yml` — ce que l'assistant `fait`, ce qu'il `ne_fait_pas`,
  les `droits` par rôle et trois `suggestions` par préfixe de route.

Les deux sont **générés par le skill Claude Code `assistant-manuel`**
(`.claude/skills/assistant-manuel/SKILL.md`), **jamais rédigés ni retouchés à la main** : le format est
celui de `backend/fastapi_ia/assistant/README.md` (AIC5 — tant qu'il n'existe pas, le skill s'arrête).
Les fichiers voyagent dans l'image fastapi par `COPY . /app/` : un merge suffit, rien à déployer à part.

## Le prompt enregistré

```
run the assistant-manuel skill (.claude/skills/assistant-manuel/SKILL.md)
```

Rien d'autre : le skill porte les sources, l'inventaire, la vérification de parité et la livraison.

## Sur quel compte

**L'abonnement Claude de Reda** (Claude Code), jamais une clé API : le manuel sert Reda (outillage du
dépôt), il ne répond à aucun commercial. Avant un `claude -p` local, retirer `ANTHROPIC_API_KEY` de
l'environnement (sinon la passe est facturée à l'API — même réflexe que `scripts/nightly-qa.ps1`) et ne
jamais passer `--bare`.

## Fréquence

- **Chaque semaine** (le lundi matin) ;
- **après tout merge** qui touche les routes (`frontend/src/**/routes*`, `urls.py`), les permissions
  (`backend/django_core/apps/roles/permissions_registre.py`), le registre d'actions
  (`backend/django_core/apps/*/agent_actions.py` et les actions natives de
  `backend/django_core/apps/agent/registry.py`) ou les domaines de l'assistant
  (`backend/fastapi_ia/app/services/chargeur_outils.py`, écrans d'`erp.ouvrir` dans
  `apps/agent/contract_samples/assistant_ecrans.json`) — sinon le manifeste ne couvre plus le registre
  et le prochain passage échoue à la parité.

## Ce que couvre la régénération

- **Toutes les clés enregistrées**, sous leurs trois formes : `AgentAction(key='…')` littéral d'un
  `apps/*/agent_actions.py`, actions natives de `apps/agent/registry.py` (`erp.ouvrir`,
  `crm.client.create`, `reporting.assistant.diagnostic`…) et clés construites par une fabrique
  (`_action('taches.…', …)` de `apps/taches/agent_actions.py`). L'ancien contrôle ne lisait que la
  première forme : il ignorait `erp.ouvrir` et les `taches.*`.
- **Les domaines** : l'assistant (moteur natif) charge ses outils par domaine (`chargeur_outils.DOMAINES`)
  autour d'un noyau toujours présent ; `erp.ouvrir` rend un bouton vers un écran de la liste fermée,
  pour tout geste qui reste humain, et n'écrit rien. Le manuel le dit en une section courte.
- **Ce qui n'y va pas** : les procédures propres à un domaine (comment l'assistant enchaîne ses outils)
  vivent dans `backend/fastapi_ia/app/services/consignes_domaines.py`, servies au chargement du domaine.
- **Étiquettes** : le manuel est servi à tous les comptes ; une action du lot `copilote` porte
  « [copilote activé] », une action réservée au moteur natif « [copilote activé, moteur natif] ».
- **Budget** : +10 000 caractères au plus par régénération (le prompt système est refusé au-delà de
  60 000 tokens).

## Planification

Au choix, une seule des deux :

1. **Tâche planifiée cloud** (Claude Code, 1 × / semaine) avec le prompt enregistré. Elle travaille sur
   le dépôt GitHub seulement (aucun accès à `api.taqinor.ma`, inutile ici) et ouvre la PR elle-même.
2. **Local** (Windows, planificateur de tâches) :
   ```powershell
   Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
   claude -p "run the assistant-manuel skill (.claude/skills/assistant-manuel/SKILL.md)" --model opus
   ```

## Vérification de parité

`capacites.yml` liste **chaque clé enregistrée et rien d'autre**. Le skill **échoue** (§6 du SKILL.md)
si une clé du registre (les trois formes ci-dessus) manque à la section `fait`, si `fait` cite une clé
que le registre n'a pas (clé d'un plan pas encore construite, clé retirée), si une action est déclarée
hors des sources lues, si une des quatre clés (`fait`, `ne_fait_pas`, `droits`, `suggestions`) manque,
si le manuel grossit de plus de 10 000 caractères, ou s'il sort de 15 000 – 60 000 tokens (plafond de
la garde AIC5). Rouge ⇒ on corrige la génération, jamais le contrôle.

## Sortie

Une PR **docs-only** limitée aux deux fichiers sous `backend/fastapi_ia/assistant/`, mise en file par
`gh pr merge --auto --merge`. L'en-tête du manuel porte le SHA de `main` et la date de génération.
