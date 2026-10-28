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
  manque au manifeste, livre UNE PR docs-only. Invoquer sur « run the
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
3. **Rien de confidentiel côté client.** `prix_achat` / marge n'apparaissent QUE dans `ne_fait_pas`
   (l'assistant ne les donne jamais). Aucun secret, aucune clé, aucune URL interne d'administration.
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
| `backend/django_core/apps/*/agent_actions.py` | les actions propose→confirme (`AgentAction(key=…)`) → `fait` (actions) |
| `backend/django_core/apps/roles/permissions_registre.py` | codes de permission et listes par rôle → `droits` |
| `frontend/src/features/crm/relances/parcours_suivi.json` | la cadence de suivi (étapes, relances, délais) |
| `backend/django_core/apps/crm/contract_samples/controle_suivi.json` | les règles de mesure du contrôle du suivi |
| `backend/django_core/apps/ged/fixtures/guide_visite_suivi_commercial.html` | le guide visite / suivi commercial (version GED) |
| `docs/claude-memory/` (MEMORY.md puis les fichiers utiles) | décisions fondateur : règles du devis, relances, ce qui se fait hors ERP |

Délègue la lecture volumineuse à des sous-agents **sonnet** (un par source lourde) qui rendent un
résumé structuré ; l'orchestrateur assemble. Jamais un sous-agent sans `model:`.

## 3. Inventaire mécanique (ce que le manifeste DOIT couvrir)

```bash
PYTHONIOENCODING=utf-8 python - <<'EOF'
import ast, importlib.util, pathlib, json
racine = pathlib.Path("backend/django_core")
cles = []
for f in sorted(racine.glob("apps/*/agent_actions.py")):
    for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "AgentAction":
            cles += [k.value.value for k in n.keywords if k.arg == "key" and isinstance(k.value, ast.Constant)]
spec = importlib.util.spec_from_file_location("pr", racine / "apps/roles/permissions_registre.py")
pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)
roles = {n[:-len("_PERMISSIONS")]: getattr(pr, n) for n in dir(pr) if n.endswith("_PERMISSIONS") and n != "ALL_PERMISSIONS"}
print(json.dumps({"actions": cles, "permissions": len(pr.ALL_PERMISSIONS), "roles": sorted(roles)}, indent=1))
EOF
```

## 4. Écrire `backend/fastapi_ia/assistant/manuel.md`

- **En-tête** : `Généré par le skill assistant-manuel — main <SHA> — <DATE> — ne pas modifier à la main.`
- 15 000 à 30 000 tokens (≈ 60 000 à 120 000 caractères), **jamais plus de 60 000 tokens** (garde AIC5).
- Plan, par rôle (commercial, commercial terrain, responsable commercial, technicien, administration
  ventes) : « comment on fait X dans TAQINOR » sur le parcours **lead → fiche → cadence → visite →
  devis → signature → facture** ; les règles du devis (marchés résidentiel / industriel-commercial /
  agricole, TTC à l'écran, `/proposal` seul chemin du PDF client, remise et seuil d'approbation) ; les
  relances (cadence de `parcours_suivi.json`) ; le contrôle du suivi ; **ce qui se fait ailleurs que
  dans l'ERP** (ex. Odoo manuel, envoi WhatsApp par le commercial lui-même).
- Phrases courtes, en français, à l'impératif ; chaque procédure cite l'écran (route) et le bouton.

## 5. Écrire `backend/fastapi_ia/assistant/capacites.yml` (format = README AIC5)

- `fait` : **une entrée par clé du registre d'actions** (inventaire §3, 100 %) + une entrée par écran
  de CODEMAP §4 utile à un commercial.
- `ne_fait_pas` : liste explicite — envoi d'e-mails ou de WhatsApp par l'assistant (il PRÉPARE, le
  commercial envoie), prix d'achat / marge, suppressions, export comptable, modification de statut
  sans confirmation de l'utilisateur, tout ce qui n'est pas dans `fait`.
- `droits` : lus de `permissions_registre.py` (rôle → codes), jamais réécrits de mémoire.
- `suggestions` : trois questions par préfixe de route (`/crm`, `/ventes`, `/installations`, `/sav`,
  `/stock`…), dont « Mon matin » pour `/crm`.

## 6. Vérification de parité et de taille (le skill ÉCHOUE si rouge)

```bash
PYTHONIOENCODING=utf-8 python - <<'EOF'
import ast, pathlib, sys
racine = pathlib.Path("backend/django_core")
cles = {k.value.value for f in racine.glob("apps/*/agent_actions.py")
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "AgentAction"
        for k in n.keywords if k.arg == "key" and isinstance(k.value, ast.Constant)}
dossier = pathlib.Path("backend/fastapi_ia/assistant")
manifeste = (dossier / "capacites.yml").read_text(encoding="utf-8")
fait = manifeste.split("ne_fait_pas:")[0]
manque = sorted(c for c in cles if c not in fait)
tokens = len((dossier / "manuel.md").read_text(encoding="utf-8")) // 4
for cle in ("fait:", "ne_fait_pas:", "droits:", "suggestions:"):
    if cle not in manifeste:
        manque.append(f"clé de manifeste absente : {cle}")
print(f"registre : {len(cles)} clé(s) ; manquantes au manifeste : {manque or 'aucune'} ; manuel ≈ {tokens} tokens")
sys.exit(1 if manque or tokens > 60000 or tokens < 15000 else 0)
EOF
```

Rouge ⇒ corriger la génération (jamais le contrôle) et relancer §6.

## 7. Livrer

PR **docs-only** limitée à `backend/fastapi_ia/assistant/manuel.md` et `capacites.yml` (les fichiers
voyagent dans l'image fastapi par `COPY . /app/`) : commit `assistant-manuel : régénération <DATE>
(main <SHA9>)`, `gh pr create`, puis `gh pr merge --auto --merge` (merge queue ; jamais
`update-branch`, jamais de deploy — Reda déploie). Rapport en trois lignes : SHA source, nombre de clés
couvertes, taille du manuel.
