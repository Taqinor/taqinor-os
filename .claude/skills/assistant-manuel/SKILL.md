---
name: assistant-manuel
description: >-
  Génère (jamais à la main) le manuel de l'assistant IA des commerciaux
  `backend/fastapi_ia/assistant/manuel.md` (« comment on fait X dans TAQINOR »,
  par rôle) et son manifeste `backend/fastapi_ia/assistant/capacites.yml`
  (`fait` / `ne_fait_pas` / `droits` / `suggestions`) depuis le dépôt : CODEMAP §4,
  le registre d'actions `apps/*/agent_actions.py`, `apps/roles/permissions_registre.py`,
  la table du parcours de suivi, le contrat du contrôle du suivi, le guide GED et
  `docs/claude-memory/`. Tourne sur l'ABONNEMENT Claude de Reda (Claude Code, jamais
  une clé API dans l'environnement, jamais `--bare`), échoue si une clé du registre
  manque au manifeste ou si le manifeste cite une clé absente du registre (actions
  natives de `apps/agent/registry.py` et clés construites par une fabrique comprises),
  livre UNE PR docs-only. Invoquer sur « run the
  assistant-manuel skill », « régénère le manuel de l'assistant », chaque semaine
  (tâche planifiée) et après tout merge qui touche routes, permissions ou
  `agent_actions.py` (AIC50 ; mode d'emploi : docs/assistant-manuel.md).
---

# assistant-manuel — le manuel et le manifeste de l'assistant (AIC50)

Le manuel et le manifeste sont lus par l'assistant de l'ERP (prompt SYSTÈME en cache 1 h, AIC5). Ils
sont **toujours régénérés par ce skill**, jamais rédigés ni retouchés à la main : une retouche manuelle
diverge du code au premier merge suivant. Mode d'emploi, fréquence et planification :
`docs/assistant-manuel.md`.

## 0. Garde-fous (avant toute chose — un seul manquement = ARRÊT)

1. **Abonnement seulement.** Ce skill tourne dans Claude Code, sur l'abonnement de Reda, pour Reda. Si
   `ANTHROPIC_API_KEY` est dans l'environnement d'un `claude -p`, la passe est facturée à l'API : le
   lanceur la retire AVANT (même réflexe que `scripts/nightly-qa.ps1`). Jamais `--bare`. Jamais ce
   skill derrière une requête d'un commercial : il ne répond à personne, il écrit deux fichiers.
2. **Aucune donnée personnelle.** Le manuel décrit des PROCÉDURES : aucun nom, téléphone, e-mail,
   adresse, montant ou identifiant d'un client, d'un lead ou d'un employé réel — jamais un prénom codé
   en dur (« le responsable du lead », pas « Meryem »). Les exemples sont génériques.
3. **Rien de confidentiel côté client.** `prix_achat` / marge : jamais dans un texte client ; en interne
   SEULEMENT à un rôle qui a `prix_achat_voir` / `marge_voir` (décision de Reda du 19/11/2026, re-prouvée au
   L4 du 21/11 : le Directeur se les voyait refuser) — `ne_fait_pas` dit « à un rôle sans le droit », jamais
   « jamais ». Aucun manuel ne contient un prix d'achat réel. Aucun secret, aucune clé, aucune URL interne
   d'administration.
4. **Le contrat du format vient d'AIC5.** Lire `backend/fastapi_ia/assistant/README.md` (format des
   deux fichiers, clés de `capacites.yml`, plafond de taille). **Absent ⇒ ARRÊT** : « BLOQUÉ : attend
   AIC5 (contrat du format `backend/fastapi_ia/assistant/README.md`) » — ne jamais inventer le format
   (règle CONTRAT D'ABORD, CLAUDE.md).
5. Chiffres : seulement ceux lus dans le dépôt (règle « faits vérifiés ») ; une règle du devis citée
   l'est avec sa source (`fichier::symbole`) dans un commentaire HTML `<!-- source : … -->`.

## 1. Point de départ

```bash
git fetch origin main && git switch -c docs/assistant-manuel-$(date +%Y%m%d) origin/main
SHA=$(git rev-parse origin/main); DATE=$(date +%Y-%m-%d)
```

## 2. Sources (toutes lues, dans cet ordre — rien d'autre)

| Source | Ce qu'on en tire |
|---|---|
| `docs/CODEMAP.md` §4 (et §5 pour les routes front) | les écrans et endpoints par app → `fait` (écrans) |
| `backend/django_core/apps/*/agent_actions.py` | les actions propose→confirme (`AgentAction(key=…)`, et les clés passées à une fabrique comme `_action('taches.…', …)` de `apps/taches/agent_actions.py`) → `fait` (actions) |
| `backend/django_core/apps/agent/registry.py` | les actions NATIVES du registre (`erp.ouvrir`, `crm.client.create`, `reporting.assistant.diagnostic`…), le `NOYAU`, le lot `copilote` et `natif_seul` (étiquettes de §4) |
| `backend/fastapi_ia/app/services/chargeur_outils.py` | les DOMAINES chargeables (`DOMAINES`, `LIBELLES`, `AUSSI_DANS`, `ECRANS`) → la section « Domaines » du manuel |
| `backend/django_core/apps/agent/contract_samples/assistant_ecrans.json` | la liste FERMÉE des écrans et onglets qu'`erp.ouvrir` sait ouvrir |
| `backend/django_core/apps/roles/permissions_registre.py` | codes de permission et listes par rôle → `droits` |
| `frontend/src/features/crm/relances/parcours_suivi.json` | la cadence de suivi (étapes, relances, délais) |
| `backend/django_core/apps/crm/contract_samples/controle_suivi.json` | les règles de mesure du contrôle du suivi |
| `backend/django_core/apps/ged/fixtures/guide_visite_suivi_commercial.html` | le guide visite / suivi commercial (version GED) |
| `docs/claude-memory/` (MEMORY.md puis les fichiers utiles) | décisions fondateur : règles du devis, relances, ce qui se fait hors ERP |

Délègue la lecture volumineuse à des sous-agents **sonnet** (un par source lourde) qui rendent un
résumé structuré ; l'orchestrateur assemble. Jamais un sous-agent sans `model:`.

## 3. Inventaire mécanique (ce que le manifeste DOIT couvrir)

Le registre est l'union de trois formes, toutes lues par le même script (enregistré une fois en
`/tmp/inventaire_cles.py`, réutilisé par §6) : (1) `AgentAction(key='…')` littéral dans
`apps/*/agent_actions.py` ; (2) les actions NATIVES de `apps/agent/registry.py` (même forme) ;
(3) les clés construites par une FABRIQUE — une fonction dont le corps fait `AgentAction(key=<un de
ses paramètres>)`, appelée avec la clé en littéral (`_action('taches.journee.lire', …)`). L'ancien
inventaire ne lisait que (1) : il manquait `erp.ouvrir` et les 19 `taches.*`.

```bash
cat > /tmp/inventaire_cles.py <<'EOF'
import ast, pathlib
RACINE = pathlib.Path("backend/django_core")
SOURCES = sorted(RACINE.glob("apps/*/agent_actions.py")) + [RACINE / "apps/agent/registry.py"]


def _fabriques(arbre):
    """{fonction: (position, paramètre)} des fonctions qui passent un paramètre en key=."""
    out = {}
    for fn in (n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)):
        params = [a.arg for a in fn.args.args]
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "AgentAction":
                for k in n.keywords:
                    if k.arg == "key" and isinstance(k.value, ast.Name) and k.value.id in params:
                        out[fn.name] = (params.index(k.value.id), k.value.id)
    return out


def cles_du_registre():
    cles = set()
    for f in SOURCES:
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        fabriques = _fabriques(arbre)
        for n in (n for n in ast.walk(arbre) if isinstance(n, ast.Call)):
            nom = getattr(n.func, "id", "")
            if nom == "AgentAction":
                cles |= {k.value.value for k in n.keywords if k.arg == "key" and isinstance(k.value, ast.Constant)}
            elif nom in fabriques:
                pos, param = fabriques[nom]
                valeurs = [k.value for k in n.keywords if k.arg == param] + n.args[pos:pos + 1]
                cles |= {v.value for v in valeurs if isinstance(v, ast.Constant)}
    return cles


def sources_non_couvertes():
    """Un `AgentAction(` hors des sources lues (tests exclus) = une forme que l'inventaire ignore."""
    lues = {p.resolve() for p in SOURCES}
    return sorted(str(p) for p in RACINE.glob("apps/**/*.py")
                  if "test" not in p.name and p.resolve() not in lues
                  and "AgentAction(" in p.read_text(encoding="utf-8"))
EOF
PYTHONIOENCODING=utf-8 python - <<'EOF'
import importlib.util, json, pathlib, sys
sys.path.insert(0, "/tmp")
from inventaire_cles import cles_du_registre, sources_non_couvertes
racine = pathlib.Path("backend/django_core")
spec = importlib.util.spec_from_file_location("pr", racine / "apps/roles/permissions_registre.py")
pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)
roles = {n[:-len("_PERMISSIONS")]: getattr(pr, n) for n in dir(pr) if n.endswith("_PERMISSIONS") and n != "ALL_PERMISSIONS"}
print(json.dumps({"actions": sorted(cles_du_registre()), "sources_non_couvertes": sources_non_couvertes(),
                  "permissions": len(pr.ALL_PERMISSIONS), "roles": sorted(roles)}, indent=1))
EOF
```

`sources_non_couvertes` non vide ⇒ ARRÊT : une action est déclarée hors des sources lues ; étendre
`SOURCES` (jamais deviner ses clés). Recoupement facultatif quand la pile locale tourne : `docker
compose exec django python manage.py shell -c "from apps.agent.registry import all_actions;
print(sorted(a.key for a in all_actions()))"` doit rendre exactement le même ensemble.

## 4. Écrire `backend/fastapi_ia/assistant/manuel.md`

- **En-tête** : `Généré par le skill assistant-manuel — main <SHA> — <DATE> — ne pas modifier à la main.`
- 15 000 à 30 000 tokens (≈ 60 000 à 120 000 caractères), **jamais plus de 60 000 tokens** (garde AIC5).
- Plan, par rôle (commercial, commercial terrain, responsable commercial, technicien, administration
  ventes) : « comment on fait X dans TAQINOR » sur le parcours **lead → fiche → cadence → visite →
  devis → signature → facture** ; les règles du devis (marchés résidentiel / industriel-commercial /
  agricole, TTC à l'écran, `/proposal` seul chemin du PDF client, remise et seuil d'approbation) ; les
  relances (cadence de `parcours_suivi.json`) ; le contrôle du suivi ; **ce qui se fait ailleurs que
  dans l'ERP** (ex. Odoo manuel, envoi WhatsApp par le commercial lui-même).
  Le parcours continue après la facture par les modules que l'assistant sert : visite technique,
  calepinage, chantier (pose, matériel), stock, SAV, chiffres.
- **Domaines et `erp.ouvrir`** (une section courte) : l'assistant charge ses outils PAR DOMAINE
  (`chargeur_outils.DOMAINES`, libellés `LIBELLES` recopiés tels quels) ; le noyau (`registry.NOYAU`)
  est toujours là ; `erp.ouvrir` rend un bouton « Ouvrir » vers un écran de la liste fermée
  (`assistant_ecrans.json`) pour tout geste qui reste humain — il n'écrit rien. Les PROCÉDURES propres
  à un domaine (comment l'assistant enchaîne ses outils) vivent dans
  `backend/fastapi_ia/app/services/consignes_domaines.py`, jamais dans le manuel : le manuel dit ce
  que l'UTILISATEUR fait et peut demander.
- **Étiquettes** (le manuel est servi à TOUS les comptes, copilote allumé ou non) : une action du lot
  `copilote` porte « [copilote activé] » ; une action `natif_seul` (lot `copilote`, hors `NOYAU` et
  hors `CLES_COPILOTE_VAGUE1`, `registry.py`) porte « [copilote activé, moteur natif] ».
- **Budget** : une régénération fait grossir le manuel de **10 000 caractères au plus** par rapport à
  la version de `main` (le prompt système est refusé au-delà de 60 000 tokens et le manuel en est déjà
  près) ; au-delà, resserrer les sections, jamais déborder.
- Phrases courtes, en français, à l'impératif ; chaque procédure cite l'écran (route) et le bouton.
- **Bloc FAQ du tri nocturne (AIC51)** : si le `manuel.md` existant contient un bloc
  `<!-- FAQ-TRI:debut --> … <!-- FAQ-TRI:fin -->`, le recopier TEL QUEL en fin du manuel régénéré (il est
  écrit par le skill `assistant-tri`, jamais par celui-ci) ; la taille ≤ 60 000 tokens s'applique à l'ensemble.

## 5. Écrire `backend/fastapi_ia/assistant/capacites.yml` (format = README AIC5)

- `fait` : **chaque clé enregistrée, et rien d'autre** — toute clé de l'inventaire §3 (les trois
  formes : littérale, native du registre, construite par une fabrique) y figure entre backticks, et
  aucune clé absente du registre n'y figure (ni clé d'un plan pas encore construite, ni clé retirée) ;
  plusieurs clés d'une même famille peuvent partager une entrée (comme les `taches.*`). Plus une
  entrée par écran de CODEMAP §4 utile à un commercial (routes en `/…`, jamais une clé).
- `ne_fait_pas` : liste explicite — envoi d'e-mails ou de WhatsApp par l'assistant (il PRÉPARE, le
  commercial envoie), prix d'achat / marge, suppressions, export comptable, modification de statut
  sans confirmation de l'utilisateur, tout ce qui n'est pas dans `fait`.
- `droits` : lus de `permissions_registre.py` (rôle → codes), jamais réécrits de mémoire.
- `suggestions` : trois questions par préfixe de route (`/crm`, `/ventes`, `/calepinage`, `/visites`,
  `/chantiers`, `/sav`, `/stock`…), dont « Mon matin » pour `/crm` ; une suggestion ne propose qu'un
  geste qu'une clé de `fait` sert.

## 6. Vérification de parité et de taille (le skill ÉCHOUE si rouge)

```bash
PYTHONIOENCODING=utf-8 python - <<'EOF'
import pathlib, re, subprocess, sys
sys.path.insert(0, "/tmp")
from inventaire_cles import cles_du_registre, sources_non_couvertes  # écrit en §3
cles = cles_du_registre()
dossier = pathlib.Path("backend/fastapi_ia/assistant")
manifeste = (dossier / "capacites.yml").read_text(encoding="utf-8")
fait = manifeste.split("ne_fait_pas:")[0]
citees = set(re.findall(r"`([a-z_]+(?:\.[a-z_]+)+)`", fait))
erreurs = [f"manque au manifeste : {c}" for c in sorted(cles - citees)]
erreurs += [f"cité au manifeste mais absent du registre : {c}" for c in sorted(citees - cles)]
erreurs += [f"AgentAction hors des sources lues : {s}" for s in sources_non_couvertes()]
for cle in ("fait:", "ne_fait_pas:", "droits:", "suggestions:"):
    if cle not in manifeste:
        erreurs.append(f"clé de manifeste absente : {cle}")
manuel = (dossier / "manuel.md").read_text(encoding="utf-8")
avant = subprocess.run(["git", "show", "origin/main:backend/fastapi_ia/assistant/manuel.md"],
                       capture_output=True, encoding="utf-8").stdout
if avant and len(manuel) - len(avant) > 10000:
    erreurs.append(f"manuel +{len(manuel) - len(avant)} caractères (budget +10 000)")
tokens = len(manuel) // 4
print(f"registre : {len(cles)} clé(s) ; erreurs : {erreurs or 'aucune'} ; manuel ≈ {tokens} tokens")
sys.exit(1 if erreurs or tokens > 60000 or tokens < 15000 else 0)
EOF
```

La parité joue dans les DEUX sens : `fait` liste chaque clé enregistrée et rien d'autre.

Rouge ⇒ corriger la génération (jamais le contrôle) et relancer §6.

## 7. Livrer

PR **docs-only** limitée à `backend/fastapi_ia/assistant/manuel.md` et `capacites.yml` (les fichiers
voyagent dans l'image fastapi par `COPY . /app/`) : commit `assistant-manuel : régénération <DATE>
(main <SHA9>)`, `gh pr create`, puis `gh pr merge --auto --merge` (merge queue ; jamais
`update-branch`, jamais de deploy — Reda déploie). Rapport en trois lignes : SHA source, nombre de clés
couvertes, taille du manuel.
