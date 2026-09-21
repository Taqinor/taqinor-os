"""Registre UNIQUE des apps parquées — sortie physique du périmètre MVP solaire.

Décision fondateur du 20/09/2026 : l'ERP vendu est un **MVP solaire**. 47 apps
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
  database_operations=[])``) et un ``models.py`` SANS AUCUN MODÈLE ;
* RESTE dans ``INSTALLED_APPS`` : c'est ce qui garde valide le graphe de
  migrations des apps conservées — donc jamais de squash ;
* n'expose AUCUNE url, AUCUNE tâche Celery / entrée beat, AUCUN test, AUCUN
  écran, AUCUN ``contract_samples/``, AUCUNE spec e2e ;
* ne perd AUCUNE table et AUCUNE ligne de ``django_migrations`` : la migration
  finale ne touche que l'ÉTAT Django, jamais la base
  (``database_operations=[]``). Aucun ``DROP TABLE``, jamais.

Le ``models.py`` d'une coquille : un TALON, pas forcément un fichier vide
------------------------------------------------------------------------

La règle EXACTE — celle que vérifient ``core/tests/test_parked_registry.py`` et
``scripts/parquer_app.py --verifier`` — est : **aucune classe héritant de
``models.Model``**. Le cas normal reste le fichier vide (docstring seul).

Mais les migrations sont GELÉES et conservées verbatim : quand l'une d'elles
référence un symbole du ``models.py`` de son app (``default=apps.pos.models.
_default_share_token``, ``from apps.kb.models import …``), un ``models.py`` vide
rend cette migration INIMPORTABLE — le graphe entier casse (``AttributeError``
au chargement, visible seulement dans un processus NEUF). La coquille garde donc
le strict nécessaire, recopié VERBATIM de l'original :

* les fonctions module-level servant de ``default`` / ``through`` callable ;
* les énumérations ``TextChoices``/``IntegerChoices`` référencées ;
* une classe-NAMESPACE simple (sans base Django) portant une énumération
  imbriquée quand une migration écrit ``Modele.Enum`` ;
* les imports et constantes module-level dont ces symboles dépendent.

``manage.py parquer_app`` détecte ces symboles, écrit le talon et VÉRIFIE dans
un processus neuf que le graphe de migrations charge encore avant de supprimer
quoi que ce soit. Un talon N'EST PAS du code métier : il ne revit qu'au retour
du module, où il est REMPLACÉ par le ``models.py`` archivé.

Retour d'un module = restaurer son dossier depuis :data:`ARCHIVE_REF` puis
renverser la migration d'état (``migrate <app> <n-1>``), ré-inclure ses urls et
retirer son label d'ici. Recette complète et pas-à-pas :
``docs/parked-modules.md``.

Ce module est du Python PUR : il n'importe ni Django ni aucune app, pour que les
scripts de garde qui tournent hors contexte Django puissent le lire tel quel.
"""
import ast

# Tag ET branche portant l'ERP complet AVANT toute suppression. Jamais
# supprimés : c'est la seule source de restauration du code parqué.
ARCHIVE_REF = 'archive/full-erp-2026-09-20'

# Les 47 labels sortis du MVP solaire (ordre alphabétique = ordre du plan).
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

# Regroupement des 47 labels par famille — c'est le découpage des lanes de
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
        'datarooms', 'esg', 'qhse', 'gestion_projet', 'contrats',
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
# Messages, puis l'édition « Solaire C&I / EPC » (ao + veille_ao +
# btp_chantier), puis le pack Maroc (paie, einvoice, fiscal), puis compta.
# GED était le n°2 de cette liste : décision fondateur du 21/09/2026, elle
# RESTE dans le MVP solaire (module « Documents ») — donc plus rien à faire
# revenir pour elle.
PHASE2 = (
    'chat',
    'ao',
    'veille_ao',
    'btp_chantier',
    'paie',
    'einvoice',
    'fiscal',
    'compta',
)


def modeles_declares(source):
    """Noms des classes de ``source`` qui héritent d'un ``models.Model``.

    C'est la règle EXACTE du contrat de coquille (§ « Le ``models.py`` d'une
    coquille ») : un talon peut garder fonctions, énumérations et classes-
    namespace, mais AUCUN modèle Django. L'analyse est purement syntaxique
    (``ast``) — ni Django ni import de l'app, pour que la garde hôte
    ``scripts/parquer_app.py --verifier`` la partage telle quelle.

    Est considérée comme modèle toute classe dont UNE base s'écrit ``Model``,
    ``*.Model`` (``models.Model``), ``TenantModel``/``*Model`` de ``core.models``
    ou un mixin de modèle connu (``*.Model[…]``) — en pratique : toute base dont
    le dernier segment finit par ``Model`` et n'est pas ``BaseModel``-de-schéma.
    Les énumérations (``TextChoices``, ``IntegerChoices``, ``Enum``…) et les
    classes sans base ne sont JAMAIS des modèles.
    """
    classes = [n for n in ast.walk(ast.parse(source))
               if isinstance(n, ast.ClassDef)]
    trouves = set()
    for _ in range(len(classes) + 1):
        avant = len(trouves)
        for noeud in classes:
            if noeud.name in trouves:
                continue
            for base in noeud.bases:
                dernier = (base.attr if isinstance(base, ast.Attribute)
                           else base.id if isinstance(base, ast.Name) else '')
                # ``models.Model``, ``TenantModel``, ``…Model`` de core.models,
                # ou l'héritage d'un modèle déjà repéré dans le même fichier.
                if dernier.endswith('Model') or dernier in trouves:
                    trouves.add(noeud.name)
                    break
        if len(trouves) == avant:
            break
    return sorted(trouves)


def est_parquee(label):
    """Vrai si ``label`` désigne une app parquée.

    Accepte le label court (``'voip'``) comme le chemin d'import Django
    (``'apps.voip'``) : seul le dernier segment pointé est comparé.
    """
    if not label:
        return False
    return str(label).rsplit('.', 1)[-1] in APPS_PARQUEES_SET
