from django.apps import AppConfig


class DouaneConfig(AppConfig):
    """AppConfig du module ``apps.douane`` (Groupe NTLOG).

    NTLOG10 (GARDE 2026-07-18, WIR80) : le modèle ``DossierImport`` d'origine
    ENTRE EN CONFLIT avec ``installations.DossierImport`` (FG315, déjà en
    production avec son propre viewset/tests/landed-cost FG316) — app
    possédée par le domaine PLAN_SERVICE, hors périmètre d'écriture de cette
    lane SUPPLY (CLAUDE.md : « touches ONLY the apps/dirs its contract
    owns »). La réconciliation qu'exige la GARDE (étendre l'existant OU le
    déplacer en ``SeparateDatabaseAndState``) suppose d'éditer
    ``apps/installations`` dans les deux cas — impossible depuis cette lane.
    ``DossierImport`` reste donc NON créé ici (voir ``docs/plans/
    PLAN_SUPPLY.md`` NTLOG10, marqué BLOCKED). Cette app n'héberge pour
    l'instant que le côté EXPORT (NTLOG14, ``DossierExport`` — aucun conflit
    connu), symétrique mais indépendant.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.douane'
    verbose_name = 'Douane & Import-Export'
    module_manifest = {
        'key': 'douane',
        'label': 'Douane',
        'icone': 'ship',
        'depends': [],
        'installable': True,
        'description': (
            "Dossiers d'export (incoterm, ports, pièces, statut douanier) — "
            "le volet import attend une réconciliation avec "
            "installations.DossierImport (FG315, NTLOG10 BLOCKED)."
        ),
        'categorie': 'Stock',
    }
