"""NTEXT25 — journal unifié des exécutions de la plateforme (observabilité).

Agrège, POUR UNE SOCIÉTÉ, ce que la plateforme no-code a réellement fait :

* ``automatisation`` — les ``automation.AutomationRun`` (une ligne par action,
  étapes multi-séquence comprises) ;
* ``rapport`` — la dernière exécution de chaque ``reporting.RapportAbonnement``
  (le modèle porte son propre statut, pas un journal par run : on expose ce
  qu'il sait) ;
* ``extension`` — les installations/désinstallations
  (``extensions.ExtensionInstall``).

AUCUN nouveau modèle : on relit les journaux existants. Les modèles des autres
apps sont résolus à l'exécution (``django.apps.apps.get_model``) — ce module ne
crée aucune arête d'import cross-app.
"""
import logging

logger = logging.getLogger(__name__)

__all__ = ['TYPES', 'journal_plateforme']

TYPES = ('automatisation', 'rapport', 'extension')

#: Statuts considérés comme un SUCCÈS (le reste est un échec/attente).
_STATUTS_OK = {'success', 'noop', 'ok', 'non_configure', 'installe',
               'desinstalle', 'sans_destinataire'}

#: Borne dure : le journal ne renvoie jamais plus que ça.
LIMITE_MAX = 200


def _modele(label):
    from django.apps import apps as django_apps

    app_label, nom = label.split('.', 1)
    return django_apps.get_model(app_label, nom)


def _entree(type_, libelle, statut, horodatage, message):
    statut = (statut or '').strip()
    return {
        'type': type_,
        'libelle': libelle or '',
        'statut': statut,
        'succes': statut.lower() in _STATUTS_OK,
        'horodatage': horodatage,
        'message': (message or '')[:500],
    }


def _entrees_automatisation(company, limite):
    modele = _modele('automation.AutomationRun')
    lignes = (modele.objects.filter(company=company)
              .select_related('rule').order_by('-timestamp', '-id')[:limite])
    return [
        _entree('automatisation',
                getattr(ligne.rule, 'nom', '') or 'Règle supprimée',
                ligne.status, ligne.timestamp, ligne.message)
        for ligne in lignes
    ]


def _entrees_rapport(company, limite):
    modele = _modele('reporting.RapportAbonnement')
    lignes = (modele.objects.filter(company=company,
                                    derniere_execution_le__isnull=False)
              .select_related('rapport_def')
              .order_by('-derniere_execution_le', '-id')[:limite])
    entrees = []
    for ligne in lignes:
        detail = ligne.dernier_detail or {}
        message = detail.get('detail', '') if isinstance(detail, dict) else ''
        entrees.append(_entree(
            'rapport',
            getattr(ligne.rapport_def, 'titre', '') or 'Abonnement',
            ligne.dernier_statut, ligne.derniere_execution_le, message))
    return entrees


def _entrees_extension(company, limite):
    from .models import ExtensionInstall

    lignes = (ExtensionInstall.objects.filter(company=company)
              .select_related('package')
              .order_by('-updated_at', '-id')[:limite])
    entrees = []
    for ligne in lignes:
        poses = len(ligne.objets_crees or [])
        entrees.append(_entree(
            'extension',
            getattr(ligne.package, 'nom', '') or 'Package',
            ligne.statut, ligne.updated_at,
            f'{poses} objet(s) posé(s) — version '
            f'{ligne.version or "?"}.'))
    return entrees


_SOURCES = {
    'automatisation': _entrees_automatisation,
    'rapport': _entrees_rapport,
    'extension': _entrees_extension,
}


def journal_plateforme(company, *, types=None, succes=None, limite=50):
    """Timeline unifiée, la plus récente d'abord, bornée à ``limite``.

    ``types`` restreint aux catégories demandées ; ``succes`` (True/False)
    filtre sur l'issue. Une source indisponible (app retirée) n'empêche jamais
    les autres de s'afficher.
    """
    try:
        limite = max(1, min(int(limite), LIMITE_MAX))
    except (TypeError, ValueError):
        limite = 50
    demandes = [t for t in (types or TYPES) if t in _SOURCES] or list(TYPES)

    entrees = []
    for type_ in demandes:
        try:
            entrees.extend(_SOURCES[type_](company, limite))
        except Exception:  # pragma: no cover - source indisponible
            logger.warning('journal: source %s indisponible', type_,
                           exc_info=True)

    if succes is not None:
        entrees = [e for e in entrees if e['succes'] is bool(succes)]
    entrees.sort(key=lambda e: (e['horodatage'] is not None, e['horodatage']),
                 reverse=True)
    return entrees[:limite]
