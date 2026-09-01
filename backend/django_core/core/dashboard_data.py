"""NTDATA32/33 — données d'un dashboard sous filtres GLOBAUX + drill-down.

Couche de FONDATION : ``core`` n'importe AUCUNE app métier (contrat
import-linter ``core-foundation-is-a-base-layer``). Tout passe par
``core.data_explorer`` — datasets ENREGISTRÉS par les apps, querysets déjà
scopés société, liste blanche de champs.

NTDATA32 — filtres globaux
--------------------------

``Dashboard.layout`` reste un JSON OPAQUE (aucune migration) ; on y reconnaît
désormais deux clés facultatives :

    {
      "widgets": [
        {"id": "ca_mensuel", "titre": "CA par mois",
         "dataset": "ventes_devis",
         "spec": {"group_by": ["mois_creation"], "aggregates": [...]},
         "filtres_globaux": {"periode": "mois_creation",
                             "responsable": "responsable"}}
      ],
      "global_filters": {"periode": {"debut": "2026-01-01",
                                     "fin": "2026-03-31"},
                         "responsable": 12}
    }

Un filtre global ne s'applique à un widget QUE si ce widget déclare, dans
``filtres_globaux``, le champ de SON dataset qui porte cette dimension : deux
datasets ne nomment pas « la date » pareil, et filtrer à l'aveugle sur un champ
deviné produirait un chiffre faux. Un widget qui ne déclare rien reste donc
inchangé plutôt que d'être filtré de travers.

La validation finale reste celle de ``data_explorer`` : tout champ hors liste
blanche du dataset lève ``ChampNonAutorise`` — remontée en erreur DU WIDGET
concerné (un widget mal câblé ne doit pas blanchir tout le dashboard).

NTDATA33 — drill-down
---------------------

``registre_drill`` associe un dataset à (a) le champ identifiant de ses lignes
et (b) une route front de l'écran détail de l'app propriétaire. Chaque app
l'enregistre depuis son ``apps.py``/``bi_datasets.py``, exactement comme elle
enregistre son dataset : ``core`` ne connaît donc aucune route en dur.
"""
from __future__ import annotations

from . import bi_cache
from . import data_explorer

# Clé de filtre global réservée à une PÉRIODE (bornes debut/fin) — toutes les
# autres clés sont des égalités simples.
CLE_PERIODE = 'periode'


class FiltreGlobalInvalide(Exception):
    """Filtres globaux mal formés (corps/paramètre illisible)."""


def normaliser_filtres(globaux):
    """Nettoie les filtres globaux (dict) : vide/None → ignoré.

    Lève ``FiltreGlobalInvalide`` si la structure n'est pas un dict ou si la
    période n'est pas un dict ``{debut, fin}``.
    """
    if globaux in (None, ''):
        return {}
    if not isinstance(globaux, dict):
        raise FiltreGlobalInvalide(
            'Les filtres globaux doivent être un objet JSON.')
    out = {}
    for cle, valeur in globaux.items():
        if cle == CLE_PERIODE:
            if not isinstance(valeur, dict):
                raise FiltreGlobalInvalide(
                    'La période doit être un objet { debut, fin }.')
            periode = {k: v for k, v in valeur.items()
                       if k in ('debut', 'fin') and v not in (None, '')}
            if periode:
                out[cle] = periode
            continue
        if valeur in (None, ''):
            continue
        out[cle] = valeur
    return out


def spec_filtree(widget, globaux):
    """Spec du widget avec les filtres globaux réinjectés (copie, jamais en place)."""
    spec = dict(widget.get('spec') or {})
    mapping = widget.get('filtres_globaux') or {}
    if not globaux or not mapping:
        return spec
    filters = dict(spec.get('filters') or {})
    for cle, valeur in globaux.items():
        champ = mapping.get(cle)
        if not champ:
            continue  # ce widget ne porte pas cette dimension → non filtré.
        if cle == CLE_PERIODE:
            if valeur.get('debut'):
                filters[f'{champ}__gte'] = valeur['debut']
            if valeur.get('fin'):
                filters[f'{champ}__lte'] = valeur['fin']
        else:
            filters[champ] = valeur
    spec['filters'] = filters
    return spec


def executer_dashboard(dashboard, company, user, globaux=None):
    """Exécute TOUS les widgets d'un dashboard sous les mêmes filtres globaux.

    ``globaux=None`` → on prend ceux enregistrés dans le ``layout``. Le résultat
    est une réponse UNIQUE : une seule requête HTTP rafraîchit tout le
    dashboard quand la période change.
    """
    from .formula import FormulaError

    layout = dashboard.layout or {}
    widgets = layout.get('widgets') or []
    effectifs = normaliser_filtres(
        layout.get('global_filters') if globaux is None else globaux)

    resultats = []
    for index, widget in enumerate(widgets):
        if not isinstance(widget, dict):
            continue
        ident = widget.get('id') or f'widget-{index}'
        dataset = widget.get('dataset')
        entree = {'id': ident, 'titre': widget.get('titre', ''),
                  'dataset': dataset}
        if not dataset:
            entree['erreur'] = 'Widget sans dataset.'
            resultats.append(entree)
            continue
        spec = spec_filtree(widget, effectifs)
        # NTDATA36 — pré-agrégation OPT-IN : un widget déclaré lourd sert
        # depuis le cache (TTL) ; les autres restent frais à chaque appel.
        ttl = bi_cache.ttl_du_widget(widget)
        try:
            if ttl:
                rows, statut = bi_cache.run_query_cache(
                    dataset, company, user, spec, ttl=ttl)
            else:
                rows, statut = data_explorer.run_query(
                    dataset, company, user, spec), ''
        except (data_explorer.DatasetInconnu,
                data_explorer.ChampNonAutorise, FormulaError) as exc:
            entree['erreur'] = str(exc)
        else:
            entree['rows'] = rows
            if statut:
                entree['cache'] = statut
        resultats.append(entree)
    return {'filtres_globaux': effectifs, 'widgets': resultats}


# ---------------------------------------------------------------------------
# NTDATA33 — registre de drill-down : dataset → identifiant + route détail.

_DRILL: dict[str, dict] = {}


def register_drill(dataset, *, id_field='id', route=''):
    """Déclare comment forer un dataset jusqu'à l'enregistrement.

    ``id_field`` = champ identifiant (doit appartenir à la liste blanche du
    dataset) ; ``route`` = gabarit de route front de l'écran détail de l'app
    PROPRIÉTAIRE, ex. ``'/ventes/devis/{id}'``. Appelé par l'app, jamais par
    ``core`` (aucune route métier en dur dans la fondation).
    """
    if not dataset:
        raise ValueError('Drill-down : nom de dataset requis.')
    _DRILL[dataset] = {'id_field': id_field or 'id', 'route': route or ''}


def get_drill(dataset):
    """Configuration de drill-down d'un dataset (défaut prudent si absente)."""
    return _DRILL.get(dataset) or {'id_field': 'id', 'route': ''}


def list_drill():
    """Catalogue des mappings dataset → route détail (rendu stable)."""
    out = [{'dataset': name, **cfg} for name, cfg in _DRILL.items()]
    out.sort(key=lambda d: d['dataset'])
    return out


def lien_profond(route, identifiant):
    """Lien profond vers l'écran détail (``''`` si l'app n'a pas de route)."""
    if not route:
        return ''
    if '{id}' in route:
        return route.replace('{id}', str(identifiant))
    return f"{route.rstrip('/')}/{identifiant}"


def drill(dataset, company, user, *, group_by=None, filters=None, limit=200):
    """NTDATA33 — lignes SOUS-JACENTES d'une cellule de pivot / point de graphe.

    ``group_by`` porte les VALEURS de regroupement de la cellule cliquée
    (``{'mois_creation': '2026-03', 'statut': 'envoye'}``) ; elles deviennent
    des filtres d'égalité. Le résultat est la liste des identifiants + leur
    lien profond. La liste blanche du dataset et le scoping société
    s'appliquent tels quels (``data_explorer.run_query``).
    """
    cfg = get_drill(dataset)
    id_field = cfg['id_field']
    spec_filters = dict(filters or {})
    for champ, valeur in (group_by or {}).items():
        spec_filters[champ] = valeur
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 200
    lim = max(1, min(lim, 1000))
    rows = data_explorer.run_query(dataset, company, user, {
        'select': [id_field],
        'filters': spec_filters,
        'limit': lim,
    })
    ids = [r.get(id_field) for r in rows if r.get(id_field) is not None]
    return {
        'dataset': dataset,
        'id_field': id_field,
        'route': cfg['route'],
        'nb': len(ids),
        'enregistrements': [
            {'id': i, 'lien': lien_profond(cfg['route'], i)} for i in ids
        ],
    }


def _reset_drill_for_tests() -> None:
    """Réinitialise le registre de drill-down (tests uniquement)."""
    _DRILL.clear()
