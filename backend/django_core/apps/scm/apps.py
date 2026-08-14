from django.apps import AppConfig


class ScmConfig(AppConfig):
    """AppConfig du module « apps.scm » (Groupe NTSCM — planification supply
    chain : prévision de demande, politiques de stock ABC/stock de sécurité,
    cycle S&OP mensuel).

    Couche PLANIFICATION posée AU-DESSUS de l'exécution `apps.stock` déjà en
    place (réappro basique, RFQ, DemandeAchat, transferts, scorecard
    fournisseur) — cette app ne fait QUE la planification/suggestion, jamais
    l'exécution transactionnelle finale (qui reste
    `stock.BonCommandeFournisseur` / `stock.TransfertStock`). Toute lecture de
    `apps.stock` passe par son `selectors.py`/`services.py`, jamais un import
    de modèle (frontière cross-app, CLAUDE.md).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scm'
    verbose_name = 'Planification supply chain'
    module_manifest = {
        'key': 'scm',
        'label': 'Planification supply chain',
        'icone': 'trending-up',
        'depends': ['stock'],
        'installable': True,
        'description': (
            "Prévision de demande saisonnière, événements d'impact, "
            "classification ABC, politiques de stock (ROP/stock de sécurité "
            "au niveau de service), tableau de bord de réappro consolidé et "
            "cycle S&OP mensuel (demande/offre/finance)."
        ),
        'categorie': 'Stock',
    }
