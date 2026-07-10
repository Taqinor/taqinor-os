"""ARC28 — Registre plateforme : un manifeste ``PLATFORM`` par app (la leçon Odoo).

PLAYBOOK — « déclarer une fois, apparaître partout »
====================================================
Aujourd'hui, chaque « surface » transverse (recherche globale, chatter/records,
champs personnalisés, import/export, actions agentiques, automatisations,
KPI/rapports) exige un CÂBLAGE MANUEL par app : un modèle hard-codé dans
``reporting/search.py``, un couple ajouté à ``records.ALLOWED_TARGETS``, un membre
d'énum dans ``customfields``, une entrée ``dataimport``, un module d'actions
agent, un ``DATE_TRIGGER_TARGETS`` d'automatisation, un agrégat de reporting… Cette
dispersion est la cause des « trous » (un modèle importable mais introuvable en
recherche, chatter-isé mais sans champ personnalisé).

La CONVENTION ARC28 renverse la charge : **chaque app déclare UNE fois** ce
qu'elle expose, dans un fichier ``apps/<x>/platform.py`` exposant un dict
``PLATFORM`` ::

    # apps/<x>/platform.py
    PLATFORM = {
        'module': 'crm',                 # clé ModuleToggle (défaut = app_label)
        'searchable_models': ['crm.lead', 'crm.client'],
        'record_targets': ['crm.lead', 'crm.client'],
        'customfield_models': ['lead', 'client'],
        'import_specs': ['lead', 'client'],
        'agent_actions_module': 'apps.crm.agent_actions',
        'automation_state_fields': [
            {'model': 'crm.lead', 'field': 'relance_date'},
        ],
        'kpi_providers': ['crm_leads'],
    }

``core`` COLLECTE ces manifestes GÉNÉRIQUEMENT — comme ``core.modules``
collecte ``module_manifest`` sur les ``AppConfig`` et ``core.event_coverage``
scanne les fichiers — SANS jamais importer un modèle métier au niveau module :
il énumère les apps via ``django.apps.get_app_configs()`` puis charge
``<app>.platform`` À L'EXÉCUTION (``importlib.import_module``). Aucun ``import
apps.crm...`` statique n'apparaît dans ce fichier : le contrat import-linter
``core-foundation-is-a-base-layer`` reste vert.

GATAGE PAR ``ModuleToggle`` (étend ODX23)
-----------------------------------------
La vue par société (:func:`platform_manifests_for_company`) DROPPE le manifeste
d'un module désactivé pour la société (``core.feature_flags.modules_desactives``).
Conséquence — exactement l'intention ODX23 : **un module OFF disparaît de TOUTES
les surfaces** (recherche, chatter, champs perso, import, agent, automations,
KPI), sans que chaque surface ait à re-tester le toggle.

Les surfaces basculent sur ce registre dans des tâches séparées (ARC29-34) ; ce
module livre le REGISTRE SEUL + deux manifestes pilotes (``crm``, ``contrats``).
"""
from __future__ import annotations

import importlib


class PlatformManifestError(ValueError):
    """Erreur de validation d'un manifeste plateforme ``PLATFORM``."""


# Les 7 surfaces transverses qu'un manifeste peut alimenter. Toute clé inconnue
# dans un ``PLATFORM`` est refusée (frappe / surface non prévue = erreur nette).
SURFACE_KEYS = (
    'searchable_models',       # modèles cherchables (reporting/search.py) — 'app.model'
    'record_targets',          # cibles chatter/records (ALLOWED_TARGETS) — 'app.model'
    'customfield_models',      # modèles à champs perso (customfields enum) — 'model'
    'import_specs',            # entités import/export (dataimport) — clés libres
    'agent_actions_module',    # module dotted des actions agent — 'apps.x.agent_actions'
    'automation_state_fields',  # [{'model': 'app.model', 'field': 'statut'}]
    'kpi_providers',           # fournisseurs de KPI/agrégats (reporting) — clés libres
)

# Clés list-of-string (normalisées en listes, dédoublonnées en conservant l'ordre).
_LIST_SURFACES = frozenset({
    'searchable_models', 'record_targets', 'customfield_models',
    'import_specs', 'kpi_providers',
})
# Clés « chaîne unique ou vide » (module dotted).
_SCALAR_SURFACES = frozenset({'agent_actions_module'})
# Clés list-of-dict (chaque entrée = {'model': ..., 'field': ...}).
_DICT_LIST_SURFACES = frozenset({'automation_state_fields'})


def _dedupe(seq):
    """Liste dédoublonnée en conservant l'ordre d'apparition."""
    vus = set()
    out = []
    for item in seq:
        if item not in vus:
            vus.add(item)
            out.append(item)
    return out


def _normaliser(module_key, manifest):
    """Renvoie une copie normalisée d'un ``PLATFORM`` (défauts + validations).

    ``module_key`` : clé ``ModuleToggle`` du manifeste (déjà résolue). Lève
    ``PlatformManifestError`` sur une clé de surface inconnue ou une entrée
    ``automation_state_fields`` mal formée.
    """
    inconnues = set(manifest) - set(SURFACE_KEYS) - {'module'}
    if inconnues:
        raise PlatformManifestError(
            f"Manifeste plateforme « {module_key} » : clé(s) de surface "
            f"inconnue(s) {sorted(inconnues)} (surfaces valides : "
            f"{list(SURFACE_KEYS)}).")

    out = {'module': module_key}
    for key in SURFACE_KEYS:
        val = manifest.get(key)
        if key in _LIST_SURFACES:
            out[key] = _dedupe(list(val or []))
        elif key in _SCALAR_SURFACES:
            out[key] = val or ''
        elif key in _DICT_LIST_SURFACES:
            entries = []
            for entry in (val or []):
                if (not isinstance(entry, dict)
                        or 'model' not in entry or 'field' not in entry):
                    raise PlatformManifestError(
                        f"Manifeste « {module_key} » : chaque "
                        f"« {key} » doit être un dict "
                        "{'model': 'app.model', 'field': 'nom'} — reçu "
                        f"{entry!r}.")
                entries.append({'model': entry['model'], 'field': entry['field']})
            out[key] = entries
    return out


def _iter_platform_modules():
    """Itère ``(module_key, PLATFORM)`` pour chaque app exposant ``<app>.platform``.

    GÉNÉRIQUE : énumère ``django.apps.get_app_configs()`` puis tente
    ``importlib.import_module(f'{app_config.name}.platform')`` À L'EXÉCUTION. Une
    app sans fichier ``platform`` est simplement ignorée (``ModuleNotFoundError``
    dont le nom pointe *ce* sous-module). Le ``module`` du manifeste vaut par
    défaut ``app_config.label`` (aligné sur la clé ``ModuleToggle``/``module_manifest``).

    Aucun ``import apps.<x>`` statique : ``core`` reste app de fondation.
    """
    from django.apps import apps as django_apps

    for app_config in django_apps.get_app_configs():
        dotted = f'{app_config.name}.platform'
        try:
            mod = importlib.import_module(dotted)
        except ModuleNotFoundError as exc:
            # Ignorer UNIQUEMENT l'absence de CE sous-module ``platform`` ; un
            # ModuleNotFoundError provoqué par un import cassé À L'INTÉRIEUR du
            # fichier platform.py doit remonter (nom de module manquant différent).
            if exc.name in (dotted, f'{app_config.name}'):
                continue
            raise
        manifest = getattr(mod, 'PLATFORM', None)
        if not manifest:
            continue
        module_key = manifest.get('module') or app_config.label
        yield module_key, manifest


def collect_platform_manifests():
    """Collecte TOUS les manifestes plateforme des apps installées.

    Renvoie ``{module_key: manifeste_normalisé}``. GÉNÉRIQUE : découverte des
    fichiers ``apps/<x>/platform.py`` par ``get_app_configs()`` +
    ``importlib`` — zéro import d'app métier. Lève ``PlatformManifestError`` sur
    une clé de module dupliquée ou un manifeste invalide.
    """
    out = {}
    for module_key, manifest in _iter_platform_modules():
        norm = _normaliser(module_key, manifest)
        if module_key in out:
            raise PlatformManifestError(
                f'Clé de module plateforme dupliquée : « {module_key} ».')
        out[module_key] = norm
    return out


def platform_manifests_for_company(company, *, manifests=None):
    """Manifestes plateforme VISIBLES pour ``company`` (gatés ``ModuleToggle``).

    Étend ODX23 : un module désactivé pour la société
    (``core.feature_flags.modules_desactives``) est ABSENT du résultat — il
    disparaît donc de toutes les surfaces d'un coup. ``company=None`` (pas de
    scope) ⇒ tous les manifestes (politique FG391 : activé par défaut).
    """
    if manifests is None:
        manifests = collect_platform_manifests()
    if company is None:
        return dict(manifests)

    from core.feature_flags import modules_desactives

    desactives = modules_desactives(company)
    return {
        key: manifest
        for key, manifest in manifests.items()
        if key not in desactives
    }


# ── Agrégateurs par surface (aplatissent tous les manifestes, gatés société) ──
# Ces helpers sont ce que les surfaces (ARC29-34) appelleront à la place de leurs
# listes hard-codées. Chacun accepte ``company`` (gatage ModuleToggle) OU
# ``manifests`` (déjà collectés/gatés, pratique en test).


def _resolved(company, manifests):
    if manifests is not None:
        return manifests
    return platform_manifests_for_company(company)


def searchable_models(company=None, *, manifests=None):
    """Ensemble des modèles cherchables ``'app.model'`` déclarés (gaté société)."""
    out = set()
    for manifest in _resolved(company, manifests).values():
        out.update(manifest['searchable_models'])
    return out


def record_targets(company=None, *, manifests=None):
    """Ensemble des cibles chatter/records ``'app.model'`` déclarées (gaté société)."""
    out = set()
    for manifest in _resolved(company, manifests).values():
        out.update(manifest['record_targets'])
    return out


def customfield_models(company=None, *, manifests=None):
    """Ensemble des modèles à champs perso ``'model'`` déclarés (gaté société)."""
    out = set()
    for manifest in _resolved(company, manifests).values():
        out.update(manifest['customfield_models'])
    return out


def import_specs(company=None, *, manifests=None):
    """Ensemble des entités import/export déclarées (gaté société)."""
    out = set()
    for manifest in _resolved(company, manifests).values():
        out.update(manifest['import_specs'])
    return out


def agent_actions_modules(company=None, *, manifests=None):
    """Ensemble des modules d'actions agent déclarés (chaînes non vides, gaté société)."""
    out = set()
    for manifest in _resolved(company, manifests).values():
        if manifest['agent_actions_module']:
            out.add(manifest['agent_actions_module'])
    return out


def automation_state_fields(company=None, *, manifests=None):
    """Liste des couples ``{'model','field'}`` d'automatisation déclarés (gaté société)."""
    out = []
    for manifest in _resolved(company, manifests).values():
        out.extend(manifest['automation_state_fields'])
    return out


def kpi_providers(company=None, *, manifests=None):
    """Ensemble des fournisseurs de KPI/agrégats déclarés (gaté société)."""
    out = set()
    for manifest in _resolved(company, manifests).values():
        out.update(manifest['kpi_providers'])
    return out
