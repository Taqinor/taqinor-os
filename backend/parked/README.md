# backend/parked/ — source des 47 modules sortis du MVP solaire (SOLMVP37, 21/09/2026)

## Ce que c'est

Ce dossier contient le **code source d'AVANT coquillage** des **47 apps Django**
sorties du périmètre « un seul produit : le MVP solaire » (Groupe SOLMVP,
`docs/PLAN.md`), coquillées par SOLMVP30-36. Le founder a tranché : ce code
n'est **pas supprimé**, il est **rangé**, hors PYTHONPATH / images Docker /
linters / tests / gardes CI, mais il reste **visible dans le dépôt** — le
pendant backend de `frontend/parked/` (voir son `README.md`, même logique,
même décision fondateur).

Registre machine (source UNIQUE des 47 labels) :
[`backend/django_core/core/parked.py`](../django_core/core/parked.py)
(`APPS_PARQUEES`, `GROUPES`, `PHASE2`, `ARCHIVE_REF`). Ce fichier-ci ne
recopie aucun label : il documente le dossier, pas la liste.

## D'où vient ce code, et comment le rafraîchir

Chaque `backend/parked/<label>/` est extrait **verbatim** de la branche/tag
d'archive `archive/full-erp-2026-09-20` (`core.parked.ARCHIVE_REF`) — le
point posé sur `main` **avant** toute suppression, jamais supprimé — via
`scripts/parquer_miroir.py`, idempotent (stdlib seul, `git archive` +
`tarfile`) :

```
python scripts/parquer_miroir.py                 # rafraîchit les 47 labels
python scripts/parquer_miroir.py --label frais    # un sous-ensemble
```

Rejouer le script **vide puis réécrit** chaque `backend/parked/<label>/`
depuis le tag : il n'y a jamais de fichier périmé à la main.

## Ce qui est miroré, et ce qui ne l'est PAS

Pour chaque label : **tout le contenu original de
`backend/django_core/apps/<label>/`** au moment de l'archive — `__init__.py`,
`apps.py`, `models.py` (les vraies définitions de modèles, PAS les coquilles),
`views.py`, `serializers.py`, `services.py`, `selectors.py`, `urls.py`,
`admin.py`, `tests/`, `management/commands/`, `contract_samples/`, etc. — à
l'identique de l'inventaire par module de `docs/parked-modules.md` §3.

**`migrations/` ne bouge jamais** : elle reste, gelée et verbatim (+ la
migration finale `SeparateDatabaseAndState(state_operations=[DeleteModel…],
database_operations=[])`), sous
`backend/django_core/apps/<label>/migrations/` — c'est elle qui garde le
graphe de migrations valide pour les apps conservées (voir le contrat de
coquille, `docs/parked-modules.md` §2). Elle n'est donc **jamais dupliquée**
ici, et `__pycache__/*.pyc` sont exclus par construction (jamais suivis par
git de toute façon).

Résultat : `backend/django_core/apps/<label>/` (la coquille : trois fichiers
+ `migrations/`) et `backend/parked/<label>/` (ce miroir : tout le reste) sont
**complémentaires**, jamais redondants — leur `models.py` diffèrent
volontairement (talon vide/quasi-vide côté coquille, vraies classes
`models.Model` côté miroir).

## Hors build / lint / tests / gardes CI

Rien ici n'est importé ni exécuté :

- **PYTHONPATH** : `backend/parked/` n'est sous aucune racine de package
  Django (`backend/django_core/apps/`), donc aucun `INSTALLED_APPS` ne peut
  jamais l'atteindre.
- **Images Docker** : le contexte de build de l'image Django est
  `backend/django_core` et celui du service IA `backend/fastapi_ia` — tous
  deux des sous-dossiers `backend/` qui EXCLUENT structurellement
  `backend/parked` (c'est un dossier frère, hors contexte). Le seul contexte
  qui inclut la racine du dépôt est celui de l'image frontend
  (`docker-compose.yml`, `context: .`) : la racine `.dockerignore` ignore déjà
  tout `backend` (et porte, en plus, une ligne dédiée `backend/parked`).
- **flake8** : `.github/workflows/ci.yml` (job `backend-lint`) exclut
  `parked` au même titre que `migrations`.
- **compileall** : la commande CI cible `backend/django_core/apps`,
  `backend/django_core/erp_agentique` et `backend/fastapi_ia` — `backend/parked`
  est hors périmètre.
- **Tests Django** : la découverte de tests ne porte que sur les apps
  listées dans `INSTALLED_APPS` sous `backend/django_core/apps/` —
  `backend/parked` n'y est pas.
- **Gardes `scripts/check_*.py` et fingerprint CODEMAP** : chaque garde qui
  parcourt un périmètre plus large que `backend/django_core/apps/`
  (`scripts/check_stages.py`, `scripts/codemap_fingerprint.py`) exclut
  explicitement le nom de dossier `parked`.

## Faire revenir un module (complète `docs/parked-modules.md` §5)

La recette complète et pas-à-pas reste **`docs/parked-modules.md` §5** ; ce
qui suit est le point d'entrée local à ce dossier — les deux ne divergent
jamais, ce fichier ne fait qu'expliciter le premier pas côté fichiers :

1. **Copier le code back-end** : `backend/parked/<x>/` par-dessus
   `backend/django_core/apps/<x>/`, **hors `migrations/`** (qui n'a jamais
   bougé et reste celle de la coquille) :
   ```
   # Exemple, <x> = frais :
   cp -r backend/parked/frais/. backend/django_core/apps/frais/
   ```
   (ou, de façon équivalente et déjà écrite dans `docs/parked-modules.md` §5,
   `git checkout archive/full-erp-2026-09-20 -- backend/django_core/apps/<x>`
   puis `git checkout HEAD -- backend/django_core/apps/<x>/migrations`.)
2. **Renverser la migration d'état** : `python manage.py migrate <x> <n-1>`
   (`<n-1>` = la migration qui précède la coquille) — `database_operations=[]`,
   donc **aucune table touchée**, seul l'état Django change.
3. Supprimer le fichier de la migration-coquille (`*_solmvp_coquille.py`) une
   fois renversée, sinon le prochain `migrate` la réapplique.
4. **Ré-inclure** l'include d'urls (`erp_agentique/urls.py`) et, si le module
   en avait, ses entrées Celery beat — restaurés depuis l'archive.
5. **Retirer `<x>` de `APPS_PARQUEES`** dans `backend/django_core/core/parked.py`
   (et de `GROUPES`/`PHASE2` s'il y figurait).
6. **Re-passer les gardes** : `python scripts/parquer_app.py --verifier-tout`
   (doit maintenant ignorer `<x>`, sorti du registre), `makemigrations
   --check`, `flake8`, puis la CI complète.

Ce dossier ne fait **aucune** de ces étapes tout seul : il ne fait que garder
le code source visible et à jour pour que l'étape 1 n'ait jamais besoin d'aller
chercher l'archive à la main.

## Ce dossier n'est PAS

- Une suppression : `git log --follow` sur n'importe quel fichier ici (une
  fois le premier commit du miroir posé) retrouve son historique.
- Une copie qui dérive : `scripts/parquer_miroir.py` le rafraîchit depuis le
  tag d'archive à la demande — il n'y a rien à maintenir à la main entre deux
  rafraîchissements.
- Un module désactivable par toggle société (l'ancien mécanisme d'édition du
  Groupe SOL, supprimé par SOLMVP3) : ici, le code est physiquement hors du
  PYTHONPATH, jamais un simple masquage.
