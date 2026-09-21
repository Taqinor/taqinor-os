"""Registre UNIQUE des apps parquées — sortie physique du périmètre MVP solaire.

Décision fondateur du 20/09/2026 : l'ERP vendu est un **MVP solaire**. 49 apps
sortent PHYSIQUEMENT du code et des tests (« fully out » : pas de toggle), sans
perdre une seule ligne de données et sans fermer la porte à leur retour
(« whenever I want one back »). Ce module est la liste UNIQUE — aucune autre
copie de ces labels ne doit exister dans le dépôt. Elle est lue par la garde de
dérive modèle↔migration, ``scripts/check_platform.py``,
``scripts/plan_lanes.py``, la future garde ``scripts/check_parked_apps.py`` et
la régénération de ``docs/CODEMAP.md``.

Contrat « coquille de migrations » (le seul mécanisme de sortie autorisé)
------------------------------------------------------------------------
Une app dont le label figure dans :data:`APPS_PARQUEES` :

* ne garde sur le disque QUE ``__init__.py``, ``apps.py`` (label + manifeste
  ``parked: True``), ``migrations/`` (verbatim + UNE migration finale
  ``SeparateDatabaseAndState(state_operations=[DeleteModel…],
  database_operations=[])``) et un ``models.py`` VIDE ;
* RESTE dans ``INSTALLED_APPS`` : c'est ce qui garde valide le graphe de
  migrations des apps conservées — donc jamais de squash ;
* n'expose AUCUNE url, AUCUNE tâche Celery / entrée beat, AUCUN test, AUCUN
  écran, AUCUN ``contract_samples/``, AUCUNE spec e2e ;
* ne perd AUCUNE table et AUCUNE ligne de ``django_migrations`` : la migration
  finale ne touche que l'ÉTAT Django, jamais la base
  (``database_operations=[]``). Aucun ``DROP TABLE``, jamais.

Retour d'un module = restaurer son dossier depuis :data:`ARCHIVE_REF` puis
renverser la migration d'état (``migrate <app> <n-1>``), ré-inclure ses urls et
retirer son label d'ici. Recette complète et pas-à-pas :
``docs/parked-modules.md``.

Ce module est du Python PUR : il n'importe ni Django ni aucune app, pour que les
scripts de garde qui tournent hors contexte Django puissent le lire tel quel.
"""

# Tag ET branche portant l'ERP complet AVANT toute suppression. Jamais
# supprimés : c'est la seule source de restauration du code parqué.
ARCHIVE_REF = 'archive/full-erp-2026-09-20'

# Les 49 labels sortis du MVP solaire (ordre alphabétique = ordre du plan).
# Toute app absente d'ici est GARDÉE : ne jamais ajouter/retirer un label sans
# décision fondateur explicite.
APPS_PARQUEES = (
    'agriculture',
    'ai_governance',
    'ao',
    'assurances',
    'btp_chantier',
    'chat',
    'compta',
    'contacts',
    'contrats',
    'conversation_ai',
    'cpq',
    'credit',
    'dataquality',
    'datarooms',
    'douane',
    'ecommerce_connect',
    'education',
    'einvoice',
    'esg',
    'extensions',
    'fiscal',
    'flotte',
    'fpa',
    'frais',
    'ged',
    'gestion_projet',
    'grc',
    'hospitality',
    'immobilier',
    'innovation',
    'juridique',
    'kb',
    'litiges',
    'marketing',
    'migration',
    'mlops',
    'mrp',
    'paie',
    'pos',
    'promotions',
    'qhse',
    'rh',
    'sante',
    'scm',
    'territoires',
    'transport',
    'veille_ao',
    'voip',
)

# Même contenu en frozenset, pour l'appartenance en O(1) dans les gardes.
APPS_PARQUEES_SET = frozenset(APPS_PARQUEES)

# Regroupement des 49 labels par famille — c'est le découpage des lanes de
# coquillage (SOLMVP30 Finance … SOLMVP36 Verticaux) et celui de
# ``docs/parked-modules.md``. Dans chaque famille, l'ordre est l'ordre de
# coquillage : les DÉPENDANTS avant leurs DÉPENDANCES.
GROUPES = {
    'Finance & conformité': (
        'frais', 'fpa', 'assurances', 'einvoice', 'fiscal', 'juridique',
        'litiges', 'credit', 'compta',
    ),
    'RH': ('paie', 'flotte', 'rh'),
    'Commercial avancé': (
        'veille_ao', 'btp_chantier', 'ao', 'cpq', 'marketing', 'contacts',
        'territoires', 'voip', 'conversation_ai',
    ),
    'Opérations & services': (
        'datarooms', 'ged', 'esg', 'qhse', 'gestion_projet', 'contrats',
        'innovation', 'kb', 'chat',
    ),
    'Supply & retail': ('promotions', 'pos', 'transport', 'douane', 'scm'),
    'Technique': (
        'grc', 'dataquality', 'mlops', 'ai_governance', 'extensions',
        'migration',
    ),
    'Verticaux': (
        'agriculture', 'education', 'hospitality', 'immobilier', 'mrp',
        'sante', 'ecommerce_connect',
    ),
}

# Ordre de RETOUR décidé le 20/09/2026 (à retenir, jamais à re-décider) :
# Messages, GED, puis l'édition « Solaire C&I / EPC » (ao + veille_ao +
# btp_chantier), puis le pack Maroc (paie, einvoice, fiscal), puis compta.
PHASE2 = (
    'chat',
    'ged',
    'ao',
    'veille_ao',
    'btp_chantier',
    'paie',
    'einvoice',
    'fiscal',
    'compta',
)


def est_parquee(label):
    """Vrai si ``label`` désigne une app parquée.

    Accepte le label court (``'voip'``) comme le chemin d'import Django
    (``'apps.voip'``) : seul le dernier segment pointé est comparé.
    """
    if not label:
        return False
    return str(label).rsplit('.', 1)[-1] in APPS_PARQUEES_SET
