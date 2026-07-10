"""ARC14 — registre data-driven des modules « customfieldable ».

Avant ARC14, la cible d'un champ personnalisé (le modèle Django qui porte
``custom_data``) était un ``if/elif`` fermé dans ``serializers._module_model``
— ajouter un 9ᵉ module exigeait de modifier ``apps/customfields`` lui-même
(l'anti-leçon Odoo ``ir.model.fields``). Ce module introduit un REGISTRE :
chaque app déclare ses modèles « customfieldables » via ``register()``
(typiquement dans son ``AppConfig.ready()``, même idiome que les autres
abonnements inter-app — cf. ``apps/crm/apps.py``), et ``get_model()``/
``module_choices()`` résolvent la cible dynamiquement.

Les 8 clés NATIVES historiques (lead/client/produit/devis/installation/
ticket/document/fournisseur/employe — cf. ``CustomFieldDef.Module``) sont
pré-enregistrées ICI MÊME au chargement du module, donc AUCUNE dépendance à
l'ordre de ``ready()`` des autres apps pour elles : le comportement existant
est garanti identique, avant comme après ARC14 (non-régression).

Résolution PARESSEUSE : on enregistre un ``(app_label, model_name)``, jamais
la classe modèle elle-même (évite tout import circulaire au chargement des
apps) — la classe est résolue à la demande via ``django.apps.apps.get_model``.

FUTURE INTENT (voir docs/PLAN.md ARC31) : une prochaine tâche fera basculer
la SOURCE de peuplement de ce registre vers les manifests ``core/platform.py``
par app (``apps/<x>/platform.py`` → surface ``customfield_models``) — la
fonction ``register()`` ci-dessous restera l'API stable ; seul l'APPELANT
changera (un seul hook central au lieu d'un ``ready()`` par app pilote).
"""

# module_key -> (app_label, model_name) — résolution paresseuse (jamais la
# classe modèle elle-même, pour éviter les imports circulaires au chargement
# des apps Django).
_REGISTRY = {}

# Libellé humain optionnel par clé (pour un futur écran d'admin listant les
# modules disponibles) — purement informatif, jamais utilisé pour valider.
_LABELS = {}


def register(module_key, app_label, model_name, *, label=None):
    """Déclare qu'un modèle est « customfieldable » sous ``module_key``.

    Idempotent : un ré-enregistrement de la même clé avec la même cible ne
    lève rien (utile si ``ready()`` est appelé plusieurs fois, ex. tests) ;
    un ré-enregistrement vers une AUTRE cible est une erreur de programmation
    (deux apps ne peuvent pas se disputer la même clé de module).
    """
    existing = _REGISTRY.get(module_key)
    target = (app_label, model_name)
    if existing is not None and existing != target:
        raise ValueError(
            f"Le module « {module_key} » est déjà enregistré vers "
            f"{existing}, impossible de le réassigner à {target}.")
    _REGISTRY[module_key] = target
    if label:
        _LABELS[module_key] = label


def is_registered(module_key):
    """True si ``module_key`` a une cible enregistrée (native ou pilote)."""
    return module_key in _REGISTRY


def registered_module_keys():
    """Ensemble des clés de module actuellement enregistrées."""
    return frozenset(_REGISTRY)


def get_model(module_key):
    """Résout la classe modèle Django enregistrée pour ``module_key``.

    Renvoie ``None`` si la clé n'est pas enregistrée (comportement identique
    à l'ancien ``_module_model`` pour une clé inconnue) — jamais d'exception,
    les appelants existants testent déjà ``is None``.
    """
    target = _REGISTRY.get(module_key)
    if target is None:
        return None
    app_label, model_name = target
    from django.apps import apps as django_apps
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _register_native_modules():
    """Pré-enregistre les 8 clés natives historiques (non-régression).

    Résolution paresseuse identique aux autres entrées — ``get_model`` ne
    résout la classe qu'à l'appel, donc aucun import de modèle ici.
    """
    register('lead', 'crm', 'Lead', label='Lead')
    register('client', 'crm', 'Client', label='Client')
    register('produit', 'stock', 'Produit', label='Produit')
    # FG100 — modules opérationnels.
    register('devis', 'ventes', 'Devis', label='Devis')
    register('installation', 'installations', 'Installation', label='Chantier')
    register('ticket', 'sav', 'Ticket', label='Ticket SAV')
    # GED10 — métadonnées typées configurables sur les documents GED.
    register('document', 'ged', 'Document', label='Document GED')
    # XPLT14 — couverture des modules récents.
    register('fournisseur', 'stock', 'Fournisseur', label='Fournisseur')
    register('employe', 'rh', 'DossierEmploye', label='Employé')


_register_native_modules()
