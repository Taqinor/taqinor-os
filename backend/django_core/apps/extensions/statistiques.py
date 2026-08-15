"""NTEXT40 — statistiques d'usage de la plateforme (cockpit admin).

Compte, POUR UNE SOCIÉTÉ, ce que la plateforme no-code fait vraiment tourner :
objets personnalisés + enregistrements, règles actives + exécutions des 30
derniers jours (succès / échecs), rapports + abonnements, packages installés.

100 % LECTURE et AUCUN nouveau modèle : ce sont des ``count()`` sur les tables
existantes. Comme ``journal.py``, les modèles des autres apps sont résolus À
L'EXÉCUTION (``django.apps.apps.get_model``) — ce module ne crée aucune arête
d'import cross-app. Une app absente (ou un modèle renommé) dégrade en zéro,
jamais en 500.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

__all__ = ['FENETRE_JOURS', 'statistiques_plateforme']

#: Fenêtre d'observation des exécutions d'automatisation.
FENETRE_JOURS = 30

#: Statuts d'exécution comptés comme un SUCCÈS (mêmes valeurs que le journal
#: unifié NTEXT25 — une simulation ou un « sans effet » n'est pas un échec).
_STATUTS_SUCCES = ('success', 'noop', 'skipped', 'simulation')


def _modele(label):
    from django.apps import apps as django_apps

    app_label, nom = label.split('.', 1)
    return django_apps.get_model(app_label, nom)


def _compter(label, **filtres):
    """``count()`` défensif : un modèle absent/en erreur vaut 0."""
    try:
        return _modele(label).objects.filter(**filtres).count()
    except Exception:
        logger.warning('Statistiques plateforme : %s illisible', label,
                       exc_info=True)
        return 0


def statistiques_plateforme(company):
    """Compteurs d'usage de la plateforme pour ``company`` (dict JSON-able)."""
    depuis = timezone.now() - timedelta(days=FENETRE_JOURS)

    runs_total = _compter('automation.AutomationRun', company=company,
                          timestamp__gte=depuis)
    runs_succes = _compter('automation.AutomationRun', company=company,
                           timestamp__gte=depuis,
                           status__in=_STATUTS_SUCCES)

    return {
        'fenetre_jours': FENETRE_JOURS,
        'objets_personnalises': {
            'total': _compter('customfields.CustomObjectDef',
                              company=company),
            'actifs': _compter('customfields.CustomObjectDef',
                               company=company, actif=True),
            'champs': _compter('customfields.CustomFieldDef',
                               company=company),
            'enregistrements': _compter('customfields.CustomRecord',
                                        company=company),
        },
        'automatisations': {
            'regles': _compter('automation.AutomationRule', company=company),
            'regles_actives': _compter('automation.AutomationRule',
                                       company=company, enabled=True),
            'runs_30j': runs_total,
            'runs_30j_succes': runs_succes,
            'runs_30j_echecs': max(0, runs_total - runs_succes),
        },
        'rapports': {
            'definitions': _compter('reporting.RapportDefinition',
                                    company=company),
            'abonnements': _compter('reporting.RapportAbonnement',
                                    company=company),
            'abonnements_actifs': _compter('reporting.RapportAbonnement',
                                           company=company, actif=True),
        },
        'extensions': {
            'packages_installes': _compter('extensions.ExtensionInstall',
                                           company=company,
                                           statut='installe'),
            'installations': _compter('extensions.ExtensionInstall',
                                      company=company),
        },
        'gabarits_document': {
            'total': _compter('parametres.GabaritDocumentCustom',
                              company=company),
            'actifs': _compter('parametres.GabaritDocumentCustom',
                               company=company, actif=True),
        },
    }
