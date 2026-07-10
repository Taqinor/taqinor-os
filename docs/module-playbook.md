# Module playbook — « ajouter un module » (ARC51)

Le guide canonique pour créer un nouveau module ERP dans `backend/django_core`.
Les **8 points de câblage** (scout noyau §11) n'étaient documentés nulle part —
chaque module improvisait. Ce playbook est LEAN : une section courte par sujet.
Indexé depuis `docs/CODEMAP.md` §3.

> **Le raccourci d'abord.** `python manage.py startapp_erp <label>` (ARC42) génère
> `apps/<label>/` déjà branché sur toutes les primitives ci-dessous, puis imprime
> la checklist des 8 câblages restants. `--dry-run` imprime la checklist sans rien
> écrire. Ce playbook explique ce que la commande génère et ce qu'il reste à faire
> à la main.

---

## Les 8 points de câblage

Créer un module coûte 8 points de câblage manuels. `startapp_erp` en génère une
partie et imprime la liste complète ; les voici avec le fichier concerné :

1. **`erp_agentique/settings/base.py` — `INSTALLED_APPS`** : ajouter `'apps.<label>'`.
2. **`erp_agentique/urls.py`** : `path('api/django/<label>/', include('apps.<label>.urls'))`.
   Le 2ᵉ segment d'URL doit être la clé de module (point 6 sinon).
3. **`.importlinter`** : ajouter/étendre un contrat si le module doit rester
   découplé (string-FK only) ou est une couche fondation.
4. **`apps/roles/models.py` — `ALL_PERMISSIONS`** : ajouter les codes
   (`<label>_voir`, `<label>_gerer`, …) si le module gate lecture/écriture.
5. **Manifeste module** (`apps/<label>/apps.py` → `module_manifest`, ODX2) :
   ajuster `key`/`label`/`categorie`/`depends`/`installable`.
6. **`core/permissions.py` — `PREFIX_TO_MODULE`** : SEULEMENT si le 2ᵉ segment
   d'URL diffère de la clé de module (ex. `gestion-projet` → `gestion_projet`).
7. **Frontend — `frontend/src/features/<label>/module.config.jsx`** : nav Sidebar
   + routes lazy (auto-enregistré par `router/moduleRoutes.jsx`).
8. **`apps/<label>/platform.py`** (ARC28) + code métier : remplir chaque surface
   QUAND elle est câblée, puis coder modèle(s)/serializer/viewset/tests +
   `makemigrations <label>`.

---

## TenantModel — le socle multi-société (ARC1)

> Tout NOUVEAU modèle métier multi-société hérite de `core.models.TenantModel` ;
> pour conserver un related_name historique, redéclarer le champ `company` à
> l'identique.

`TenantModel` (dans `core/models.py`) apporte en une ligne la FK `company`
(vers `authentication.Company`) + `created_at`/`updated_at`. Son `related_name`
par défaut `'%(app_label)s_%(class)s_set'` garantit des accesseurs inverses
uniques ; un modèle converti qui doit garder un `related_name` historique
**redéclare** simplement son champ `company` dans son corps.

```python
from django.db import models
from core.models import TenantModel

class Exemple(TenantModel):
    nom = models.CharField('Nom', max_length=160)
    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['company', 'reference'], name='exemple_co_ref_uniq')]
```

`core.models` porte aussi des mixins de fondation optionnels : `SoftDeleteModel`
(corbeille/undo), et les modèles génériques workflow BPM / intégrations / e-sign
(cibles via `contenttypes`, jamais d'import métier).

---

## CompanyScopedModelViewSet — le viewset scopé (ARC2)

> Un nouveau viewset scopé société hérite de `core.viewsets.CompanyScopedModelViewSet`
> et exprime son accès d'UNE seule façon : `read_permission`/`write_permission`,
> OU `get_permissions`, OU rien (= authentifié suffit). Jamais un mélange ad hoc.

`CompanyScopedModelViewSet` (dans `core/viewsets.py`) porte `TenantMixin`
(queryset filtré sur `request.user.company` ; `perform_create`/`perform_update`
forcent `company` côté serveur — **jamais** lue du corps de la requête) et pose
`ScopedPermission` par défaut (ARC55). Contrôle d'accès :

- lecture ≠ écriture par méthode HTTP → poser `read_permission`/`write_permission` ;
- grain par action (ex. `destroy` admin-only) → surcharger `get_permissions` ;
- cas simple « authentifié suffit » → ne rien poser.

**Serializers** : ne jamais exposer `company` en écriture (elle est forcée côté
serveur) — la mettre en `read_only` ou l'omettre.

---

## Numérotation de documents (ARC6)

> `core.numbering` est la primitive fondation (ex `ventes/utils/references`,
> devenu shim). Jamais count()+1.

`count() + 1` collisionne en production (un document supprimé rétrécit le
compte). `core.numbering.next_reference(model, doc_prefix, company, ...)` prend
le plus-haut-utilisé + 1 par société+période ; `create_with_reference(...)`
enveloppe la création dans un savepoint et réessaie sur les courses de référence.

```python
from core.numbering import create_with_reference
return create_with_reference(
    Exemple, 'EX', company,
    lambda ref: serializer.save(company=company, reference=ref))
```

---

## Manifeste de module (ODX2) et platform.py (ARC28)

**`apps/<label>/apps.py`** déclare `module_manifest` (dict : `key`/`label`/
`icone`/`depends`/`installable`/`categorie`). `core.modules.collect_manifests`
le collecte génériquement → graphe de modules + gatage `ModuleToggle` +
enforcement 404 (`DisabledModuleMiddleware`). Une app fondation/technique met
`installable=False`.

**`apps/<label>/platform.py`** — « déclarer une fois, apparaître partout ». Un
dict `PLATFORM` déclare ce que l'app expose aux 7 surfaces transverses :
`searchable_models`, `record_targets`, `customfield_models`, `import_specs`,
`agent_actions_module`, `automation_state_fields`, `kpi_providers`.
`core.platform.collect_platform_manifests` les agrège génériquement (aucun
import de `core` vers l'app) ; un module désactivé pour une société disparaît de
TOUTES les surfaces d'un coup. **Règle d'honnêteté** : ne déclarer une surface
QUE si elle est réellement câblée (la matrice `core.platform_coverage` détecte
un identifiant déclaré mais absent du code de la surface).

---

## Surfaces via les primitives core

- **Chatter / records** : `ChatterViewSetMixin` (`apps/records/views.py`) donne à
  un viewset deux actions `chatter/historique` (GET) + `chatter/noter` (POST)
  adossées à `records.Activity` ; `records.services.log_activity(target, kind,
  …)` écrit une entrée. La cible doit être dans `records.ALLOWED_TARGETS`
  (`apps/records/models.py`) — jamais un modèle arbitraire.
- **Champs personnalisés** : `apps.customfields.registry.register(<model>,
  <app_label>, <ModelName>, label=…)` dans `apps.py` `ready()` (registre
  data-driven, jamais un import de `customfields.models`).
- **PDF** : `core.pdf.render_pdf(html=… | template=…, context=…, company=…,
  header=…, footer=…, upload_to=…)` rend un PDF (bytes) et, avec `upload_to`, le
  téléverse dans MinIO. **Exception rule #4** : le PDF de devis client passe
  EXCLUSIVEMENT par `apps/ventes/quote_engine/` (`/proposal`) — ne jamais ajouter
  un chemin PDF de devis alternatif.
- **Import / export** : `apps/dataimport` (import CSV/XLSX deux temps dry-run +
  commit) ; déclarer l'entité dans `PLATFORM['import_specs']`.
- **Actions agentiques** : `apps/<label>/agent_actions.py` (déclaré dans
  `PLATFORM['agent_actions_module']`), consommé par `apps/agent`.

---

## Événements — bus core.events (M6)

`core/events.py` expose des objets `django.dispatch.Signal` (bus synchrone qui
ne dépend de rien). Une app réagit au changement d'état d'une AUTRE app en s'y
abonnant dans `apps/<label>/receivers.py` (décorateur `@receiver(signal,
dispatch_uid=…)`), branché depuis `apps.py` `ready()` (`from . import
receivers`) — jamais en important les vues/modèles de l'autre app. Ex. `ventes`
émet `devis_accepted` ; `crm` s'abonne (`apps/crm/receivers.py`) pour faire
avancer l'étape du lead.

---

## Frontières services/selectors + import-linter

Entre apps de domaine métier (`apps/{crm,ventes,stock,installations,sav}`), tout
READ/WRITE cross-app passe par le `selectors.py` (lectures) ou `services.py`
(écritures/orchestration) de l'app CIBLE — ou par des FK-chaînes (string FK) —
jamais en important ses `models`/`views`. Ajouter une fonction fine au
selector/service cible et l'appeler (imports paresseux/fonction-locaux là où ils
évitent les cycles). Les imports intra-app et vers les apps de fondation (`roles`,
`records`, `authentication`, `core`, `customfields`, `parametres`, `reporting`…)
sont exemptés. **CI-enforcé (M3)** : `backend/django_core/.importlinter` + l'étape
`lint-imports` — les 5 modèles de domaine restent mutuellement découplés (string
FK only) et `core` reste une couche de base (n'importe aucune app de domaine).

---

## Conventions frontend

- **`frontend/src/features/<label>/module.config.jsx`** : un seul fichier
  auto-enregistré par `router/moduleRoutes.jsx` (glob). Il déclare `key`,
  `order`, `nav` (Sidebar gatée par `roles`), `titles` (routes.meta), et `routes`
  lazy. Aucune édition du routeur / de la Sidebar / de `routes.meta`. La nav est
  optionnelle (un module purement d'API n'en a pas).
- **`useHasPermission(code, [rôles])`** (`frontend/src/hooks/useHasPermission.js`)
  : masque une affordance que le backend refuserait ; le backend reste la seule
  garde qui compte (cohérence UX, pas de sécurité).
- **`useResource(fetcher, params?, options?)`** (`frontend/src/hooks/useResource.js`,
  ARC45) : tout nouvel écran de liste/tableau de bord charge ses données via ce
  hook (`{ data, loading, error, refetch }`, abort au démontage, params réactifs,
  `select`/`errorMessage`/`enabled`) — jamais un `useState(loading/error)` +
  `useEffect` maison. Aucune dépendance externe (TanStack Query = décision DEP
  séparée, non prise).
- **Factory API partagée** (`frontend/src/api/resource.js`, ARC44) : un module
  api se déclare via `makeResourceFactory(client, basePath)` + `unwrapList` —
  jamais une factory `{list,get,create,update,remove}` re-déclarée localement.
  `scripts/scaffold-module.mjs` (ARC43) génère module.config + api + page
  d'exemple d'un coup.
- **Coquilles** : listes sur `ListShell` ; pages détail/fiche sur `RecordShell`
  (`frontend/src/ui/module/RecordShell.jsx`, ARC46 — compose `DetailShell` et
  ajoute la save-bar optimiste opt-in `record`/`onSave` via `useOptimisticSave` ;
  slot chatter pour VX23). Réutiliser `components/` (DataTable, etc.) plutôt que
  de reconstruire — voir un module récent (`features/contrats`) comme gabarit.

> **Le câblage FE par-endpoint** (quel écran consomme quel endpoint) vit dans
> `docs/FRONTEND_GAP_PLAN.md`, pas ici — ce playbook couvre la STRUCTURE d'un
> module, pas l'inventaire endpoint-par-endpoint.

---

## Checklist finale

Après avoir généré et câblé le module :

```
python manage.py startapp_erp <label>       # génère apps/<label>/ + checklist
# … câbler les 8 points imprimés …
python manage.py makemigrations <label>     # si le module a des modèles
python manage.py check                       # système check vert
flake8 apps/<label> --max-line-length=120 --extend-ignore=E501 --exclude=migrations
```

Puis écrire de vrais tests : isolation multi-société, matrice de permissions,
logique métier des services.
