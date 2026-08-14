from django.apps import AppConfig


class MrpConfig(AppConfig):
    """AppConfig de l'app « apps.mrp » (Groupe NTMFG — Production / MRP II).

    Moteur générique de production réutilisable par toute ligne de fabrication
    (pas seulement le solaire) : postes de charge, gammes opératoires, ordres
    de fabrication capacitaires, calcul des besoins nets (MRP), ordonnancement
    à capacité finie, terminal atelier MES, coût de revient standard/réel,
    TRS/OEE. Distinct et complémentaire de l'atelier léger déjà existant
    (`installations.Kit`/`KitComposant`/`OrdreAssemblage` — kitting boutique),
    jamais reconstruit ici : mrp lit `installations`/`stock` UNIQUEMENT via
    leurs `selectors.py`/`services.py` ou par string-FK, jamais leurs models.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mrp'
    verbose_name = 'Production (MRP)'
    module_manifest = {
        'key': 'mrp',
        'label': 'Production (MRP)',
        'icone': 'wrench',
        'depends': [],
        'installable': True,
        'description': (
            "Postes de charge, gammes opératoires, ordres de fabrication "
            "capacitaires, calcul des besoins nets (MRP), ordonnancement à "
            "capacité finie, terminal atelier et coût de revient standard "
            "(Groupe NTMFG)."
        ),
        'categorie': 'Stock',
    }
