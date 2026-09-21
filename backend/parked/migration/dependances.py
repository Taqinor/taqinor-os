"""NTMIG3 — ordre de chargement dépendance-aware (graphe d'entités).

Déclare, pour chaque entité de lot, les entités qui doivent être chargées
AVANT elle (clients avant devis, produits avant devis/factures, fournisseurs
avant BCF, chantiers avant SAV — cf. le corps de la tâche NTMIG3). Fournit :

* :func:`ordonner_lots` — trie topologiquement les lots d'un projet et pose
  leur ``ordre`` ; refuse (``DependanceManquante``) un lot dont la dépendance
  n'a pas de lot dans CE projet, AVANT tout chargement ;
* :func:`verifier_ordre_pret` — NTMIG2, la garde « pas de lot N+1 avant que
  le lot N soit réconcilié ».

Entités absentes du dict :data:`DEPENDANCES` = aucune dépendance déclarée
(elles peuvent être chargées à tout moment). Ce module ne connaît QUE des
noms d'entité (chaînes) — jamais un import de modèle d'une autre app.
"""
from django.db import transaction

#: Dépendances déclarées PAR ENTITÉ CIBLE — l'entité listée doit avoir un lot
#: dans le projet AVANT l'entité clé. `equipements` a besoin des produits (le
#: SKU est résolu à l'import) ; `devis`/`factures` ont besoin des clients ET
#: des produits (lignes de document, NTMIG10/11).
DEPENDANCES = {
    'clients': (),
    'leads': (),
    'products': (),
    'fournisseurs': (),
    'vehicules': (),
    'contrats': (),
    'dossiers_rh': (),
    'equipements': ('products',),
    'devis': ('clients', 'products'),
    'factures': ('clients', 'products'),
}


class DependanceManquante(ValueError):
    """Un lot du projet déclare une dépendance dont le lot n'existe pas
    ENCORE dans ce projet — signalé avant tout chargement (NTMIG3)."""


class CycleDependances(ValueError):
    """Le graphe restreint aux entités présentes contient un cycle.

    Ne devrait jamais se produire avec :data:`DEPENDANCES` (acyclique par
    construction) : c'est un garde-fou de configuration, pas un cas utilisateur.
    """


class OrdreNonRespecte(ValueError):
    """NTMIG2 — un lot d'ordre STRICTEMENT inférieur, dans le même projet,
    n'est pas encore réconcilié : ``lot`` ne peut pas encore être chargé."""

    def __init__(self, message, lot_bloquant=None):
        super().__init__(message)
        self.lot_bloquant = lot_bloquant


def dependances_de(entite):
    """Dépendances déclarées de ``entite`` — ``()`` si l'entité est inconnue
    du DAG (aucune dépendance déclarée, jamais une erreur)."""
    return tuple(DEPENDANCES.get(entite, ()))


def dependances_manquantes(entite, entites_presentes):
    """Dépendances de ``entite`` absentes de ``entites_presentes``.

    ``[]`` si toutes sont présentes (ou si ``entite`` n'a aucune dépendance
    déclarée) — jamais une exception ici, c'est à l'appelant de décider quoi
    en faire (refuser la création du lot, ou lister l'écart).
    """
    presentes = set(entites_presentes)
    return [dep for dep in dependances_de(entite) if dep not in presentes]


def _tri_topologique(graphe):
    """Tri topologique de Kahn, déterministe (ties départagés par ordre
    alphabétique) — lève :class:`CycleDependances` si un cycle subsiste."""
    degre_entrant = {noeud: len(deps) for noeud, deps in graphe.items()}
    restant = {noeud: set(deps) for noeud, deps in graphe.items()}
    prets = sorted(n for n, d in degre_entrant.items() if d == 0)
    ordre = []
    while prets:
        noeud = prets.pop(0)
        ordre.append(noeud)
        nouveaux = []
        for autre, deps in restant.items():
            if noeud in deps:
                deps.discard(noeud)
                if not deps and autre not in ordre and autre not in prets:
                    nouveaux.append(autre)
        if nouveaux:
            prets = sorted(prets + nouveaux)
    if len(ordre) != len(graphe):
        manquants = sorted(set(graphe) - set(ordre))
        raise CycleDependances(
            'Cycle de dépendances détecté (entités concernées : '
            f"{', '.join(manquants)}).")
    return ordre


def ordonner_lots(projet):
    """NTMIG3 — trie topologiquement les lots du projet et pose leur ``ordre``.

    Refuse (:class:`DependanceManquante`) si un lot présent déclare une
    dépendance dont le lot n'existe pas ENCORE dans CE projet : ajouter un lot
    « factures » sans lot « clients » est signalé ICI, avant tout chargement —
    jamais une exécution partielle qui poserait un ``ordre`` incohérent.
    """
    from .models import LotMigration

    lots = list(LotMigration.objects.filter(
        company_id=projet.company_id, projet=projet))
    entites_presentes = {lot.entite for lot in lots}

    manquantes = []
    for lot in lots:
        for dep in dependances_manquantes(lot.entite, entites_presentes):
            manquantes.append((lot.entite, dep))
    if manquantes:
        detail = ', '.join(
            f'« {entite} » nécessite « {dep} »' for entite, dep in manquantes)
        raise DependanceManquante(f'Dépendance manquante : {detail}.')

    graphe = {
        entite: [d for d in dependances_de(entite) if d in entites_presentes]
        for entite in entites_presentes}
    ordre_topologique = _tri_topologique(graphe)
    rang = {entite: i for i, entite in enumerate(ordre_topologique)}

    with transaction.atomic():
        for lot in lots:
            nouvel_ordre = rang.get(lot.entite, 0)
            if lot.ordre != nouvel_ordre:
                lot.ordre = nouvel_ordre
                lot.save(update_fields=['ordre', 'updated_at'])
    return ordre_topologique


def lot_precedent_bloquant(lot):
    """Premier lot du même projet, d'ordre STRICTEMENT inférieur et pas
    encore réconcilié — ``None`` si la voie est libre pour charger ``lot``."""
    from .models import LotMigration

    return (LotMigration.objects
            .filter(company_id=lot.company_id, projet_id=lot.projet_id,
                    ordre__lt=lot.ordre)
            .exclude(statut=LotMigration.Statut.RECONCILIE)
            .order_by('ordre').first())


def verifier_ordre_pret(lot):
    """NTMIG2 — bloque le chargement de ``lot`` tant qu'un lot précédent
    (ordre strictement inférieur) du même projet n'est pas réconcilié.

    Appliqué au niveau des ACTIONS interactives (``charger``/``charger-odoo``/
    ``reprendre`` de ``LotMigrationViewSet``), jamais dans
    ``services.charger_lot`` lui-même : ce dernier est réutilisé en interne
    par la migration à blanc (NTMIG33) et la reprise sur incident (NTMIG38),
    deux usages non interactifs où l'ordre de déclaration du projet réel n'a
    pas à être rejoué (la migration à blanc, notamment, ne fait AUCUNE
    réconciliation formelle entre ses lots miroirs).
    """
    bloquant = lot_precedent_bloquant(lot)
    if bloquant is not None:
        raise OrdreNonRespecte(
            f'Le lot « {bloquant.entite} » (ordre {bloquant.ordre}) doit être '
            f'réconcilié avant de charger « {lot.entite} » (ordre {lot.ordre}).',
            lot_bloquant=bloquant)
