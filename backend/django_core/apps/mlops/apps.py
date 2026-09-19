from django.apps import AppConfig


class MlopsConfig(AppConfig):
    """App de FONDATION technique « MLOps par tenant » (Groupe NTAI, P3).

    Versionne, PAR SOCIÉTÉ, les hyperparamètres/seuils des scorers purs
    existants (``core/*.py`` — churn/win_proba/retard_paiement/reappro/
    anomalie, aujourd'hui codés en dur) et matérialise les signaux qu'ils
    consomment (feature store léger). N'importe AUCUNE app métier : les
    scorers lisent ces paramètres via ``apps.mlops.selectors`` avec repli sur
    les défauts code — jamais l'inverse.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mlops'
    label = 'mlops'
    verbose_name = 'MLOps (scorers par tenant)'
    module_manifest = {
        'key': 'mlops',
        'sku': 'generic',
        'label': 'MLOps (scorers par tenant)',
        'icone': 'cpu',
        'depends': [],
        # Réservé aux administrateurs : réglage technique des scorers, pas un
        # module métier qu'une société active/désactive au fil de l'eau.
        'installable': False,
        'description': (
            'Versionne par société les paramètres des scorers prédictifs '
            "(churn, probabilité de gain, retard de paiement…) et matérialise "
            'les signaux (features) qu\'ils consomment.'
        ),
        'categorie': 'Technique',
    }
