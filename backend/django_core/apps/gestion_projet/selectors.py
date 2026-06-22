"""Sélecteurs LECTURE SEULE de la Gestion de projet.

Point d'entrée cross-app : enrichissent les liens d'un projet (``ProjetLien``)
en appelant le sélecteur de l'app CIBLE quand elle en expose un — jamais en
important ses ``models``/``views`` (voir CLAUDE.md, frontière cross-app). Tous
les imports cross-app sont fonction-locaux pour éviter les cycles. Quand une app
cible n'a pas de sélecteur exploitable, on DÉGRADE proprement : on renvoie le
``libelle`` mis en cache et les ids stockés, sans rien importer.
"""
from .models import DependanceTache, Jalon, ProjetLien, Tache


def jalons_for_projet(projet):
    """Jalons d'un projet (QuerySet scopé société, ordonné par date prévue).

    Lecture seule. La société est portée par le projet : on filtre aussi sur
    ``projet.company`` par sécurité même si le FK ``projet`` la garantit déjà.
    Ordre : ``date_prevue`` croissante puis ``id`` (échéancier de facturation).
    """
    return Jalon.objects.filter(
        projet=projet, company=projet.company).order_by('date_prevue', 'id')


def taches_for_projet(projet):
    """Tâches d'un projet (QuerySet scopé société, ordonné WBS).

    Lecture seule. La société est portée par le projet : on filtre aussi sur
    ``projet.company`` par sécurité même si le FK ``projet`` la garantit déjà.
    """
    return Tache.objects.filter(
        projet=projet, company=projet.company).order_by('ordre', 'id')


def _serialize_dependance(dep, autre_tache):
    """Dict d'une arête de dépendance vue depuis une tâche (l'autre bout)."""
    return {
        'id': dep.id,
        'predecesseur': dep.predecesseur_id,
        'successeur': dep.successeur_id,
        'type_dependance': dep.type_dependance,
        'lag': dep.lag,
        'tache_id': autre_tache.id,
        'tache_libelle': autre_tache.libelle,
        'tache_code_wbs': autre_tache.code_wbs,
    }


def predecesseurs_de_tache(tache):
    """Arêtes entrantes d'une tâche (les tâches dont elle dépend).

    Lecture seule. ``tache`` est le SUCCESSEUR de chaque arête renvoyée ; on
    expose le prédécesseur (l'autre bout). QuerySet scopé société.
    """
    qs = DependanceTache.objects.filter(
        successeur=tache, company=tache.company
    ).select_related('predecesseur').order_by('id')
    return [_serialize_dependance(dep, dep.predecesseur) for dep in qs]


def successeurs_de_tache(tache):
    """Arêtes sortantes d'une tâche (les tâches qui dépendent d'elle).

    Lecture seule. ``tache`` est le PRÉDÉCESSEUR de chaque arête renvoyée ; on
    expose le successeur (l'autre bout). QuerySet scopé société.
    """
    qs = DependanceTache.objects.filter(
        predecesseur=tache, company=tache.company
    ).select_related('successeur').order_by('id')
    return [_serialize_dependance(dep, dep.successeur) for dep in qs]


def dependances_de_tache(tache):
    """Prédécesseurs ET successeurs directs d'une tâche (lecture seule).

    Renvoie ``{'predecesseurs': [...], 'successeurs': [...]}`` — base de PROJ8
    (chemin critique / CPM). Société portée par la tâche.
    """
    return {
        'predecesseurs': predecesseurs_de_tache(tache),
        'successeurs': successeurs_de_tache(tache),
    }


def _serialize_tache(tache, enfants_par_parent):
    """Construit le dict d'une tâche + ses sous-tâches (récursif, sans requête).

    ``enfants_par_parent`` est un index ``{parent_id: [Tache, ...]}`` calculé une
    seule fois par ``arbre_taches`` : la récursion ne refait AUCUNE requête.
    """
    return {
        'id': tache.id,
        'parent': tache.parent_id,
        'phase': tache.phase_id,
        'code_wbs': tache.code_wbs,
        'libelle': tache.libelle,
        'ordre': tache.ordre,
        'statut': tache.statut,
        'avancement_pct': tache.avancement_pct,
        'charge_estimee': (
            str(tache.charge_estimee)
            if tache.charge_estimee is not None else None),
        'sous_taches': [
            _serialize_tache(child, enfants_par_parent)
            for child in enfants_par_parent.get(tache.id, [])
        ],
    }


def arbre_taches(projet):
    """Arborescence WBS d'un projet : liste de dicts imbriqués (racines → feuilles).

    Lecture seule, UNE seule requête : on charge toutes les tâches du projet,
    on les indexe par ``parent_id`` et on déroule la récursion en mémoire. Une
    racine est une tâche sans ``parent`` ; chaque dict porte ses ``sous_taches``.
    """
    taches = list(taches_for_projet(projet))
    enfants_par_parent = {}
    for tache in taches:
        enfants_par_parent.setdefault(tache.parent_id, []).append(tache)
    racines = enfants_par_parent.get(None, [])
    return [_serialize_tache(racine, enfants_par_parent) for racine in racines]


def liens_for_projet(projet):
    """Liens d'un projet (QuerySet scopé société, ordonné par id).

    Lecture seule. La société est portée par le projet : on filtre aussi sur
    ``projet.company`` par sécurité même si le FK ``projet`` la garantit déjà.
    """
    return ProjetLien.objects.filter(
        projet=projet, company=projet.company).order_by('id')


def _label_devis(company, cible_id):
    """Libellé enrichi d'un devis via ``ventes.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``ventes.models`` directement.
    Renvoie le ``label`` de la fiche-carte du devis, ou None si l'app ne peut
    pas l'enrichir (devis absent / hors société / sélecteur indisponible).
    """
    try:
        from apps.ventes import selectors as ventes_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    card = None
    try:
        card = ventes_selectors.devis_card(cible_id, company)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if not card:
        return None
    return card.get('label') or None


# Enrichisseurs par type de cible. Une entrée n'existe QUE si l'app cible expose
# un sélecteur de lecture exploitable : `facture`/`ticket`/`achat` n'en ont pas
# aujourd'hui (ventes n'expose pas de carte facture, sav n'a pas de selectors,
# et le sélecteur stock ne porte pas l'achat) → ces types dégradent au libellé
# stocké, sans aucun import.
_ENRICHERS = {
    ProjetLien.TypeCible.DEVIS: _label_devis,
}


def liens_enrichis(projet):
    """Liste de dicts {id, type_cible, cible_id, libelle, source} pour un projet.

    Pour chaque lien : si l'app cible expose un enrichisseur, on s'en sert pour
    récupérer un libellé frais (``source='live'``) ; sinon — ou si l'enrichissement
    renvoie vide — on retombe sur le ``libelle`` stocké (``source='stored'``).
    Aucune exception ne remonte : un enrichisseur qui échoue dégrade au libellé
    stocké.
    """
    out = []
    for lien in liens_for_projet(projet):
        libelle = lien.libelle
        source = 'stored'
        enricher = _ENRICHERS.get(lien.type_cible)
        if enricher is not None:
            try:
                fresh = enricher(lien.company, lien.cible_id)
            except Exception:  # pragma: no cover - défensif
                fresh = None
            if fresh:
                libelle = fresh
                source = 'live'
        out.append({
            'id': lien.id,
            'type_cible': lien.type_cible,
            'cible_id': lien.cible_id,
            'libelle': libelle,
            'source': source,
        })
    return out
