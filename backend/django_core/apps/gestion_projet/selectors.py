"""Sélecteurs LECTURE SEULE de la Gestion de projet.

Point d'entrée cross-app : enrichissent les liens d'un projet (``ProjetLien``)
en appelant le sélecteur de l'app CIBLE quand elle en expose un — jamais en
important ses ``models``/``views`` (voir CLAUDE.md, frontière cross-app). Tous
les imports cross-app sont fonction-locaux pour éviter les cycles. Quand une app
cible n'a pas de sélecteur exploitable, on DÉGRADE proprement : on renvoie le
``libelle`` mis en cache et les ids stockés, sans rien importer.
"""
from datetime import date as _date
from datetime import timedelta

from django.db.models import Q, Sum

from decimal import Decimal

from .models import (
    AffectationRessource,
    BaselinePlanning,
    BudgetProjet,
    CalendrierProjet,
    DependanceTache,
    Equipe,
    Indisponibilite,
    Jalon,
    LigneBudgetProjet,
    PointAvancement,
    Projet,
    ProjetLien,
    RessourceProfil,
    Risque,
    Tache,
    Timesheet,
)


def baselines_for_projet(projet):
    """Baselines d'un projet (QuerySet scopé société, plus récentes d'abord)."""
    return BaselinePlanning.objects.filter(
        projet=projet, company=projet.company).order_by(
            '-date_creation', '-id')


def _ecart_jours(reel, baseline):
    """Écart en jours entre une date réelle et une date baseline (ou None)."""
    if reel is None or baseline is None:
        return None
    return (reel - baseline).days


def comparer_baseline(baseline):
    """Compare une BASELINE au planning COURANT (plan vs réel) — lecture seule.

    Pour chaque ligne figée de la baseline, retrouve la tâche courante (par FK)
    et calcule l'écart de DÉBUT et de FIN (en jours, positif = glissement vers
    le futur) ainsi que la dérive de charge. Une tâche supprimée depuis le
    snapshot apparaît avec ``tache=None`` (le libellé figé est conservé). Renvoie
    ``{baseline, projet, lignes: [...], glissement_max_fin}`` où
    ``glissement_max_fin`` est le plus grand retard de fin observé (0 si aucun).
    """
    lignes = []
    glissement_max = 0
    qs = baseline.lignes.select_related('tache').order_by('id')
    for ligne in qs:
        tache = ligne.tache
        reel_debut = tache.date_debut_prevue if tache else None
        reel_fin = tache.date_fin_prevue if tache else None
        reel_charge = tache.charge_estimee if tache else None
        ecart_debut = _ecart_jours(reel_debut, ligne.date_debut_prevue)
        ecart_fin = _ecart_jours(reel_fin, ligne.date_fin_prevue)
        if ecart_fin is not None and ecart_fin > glissement_max:
            glissement_max = ecart_fin
        derive_charge = None
        if reel_charge is not None and ligne.charge_estimee is not None:
            derive_charge = str(reel_charge - ligne.charge_estimee)
        lignes.append({
            'ligne': ligne.id,
            'tache': ligne.tache_id,
            'libelle': ligne.tache_libelle,
            'code_wbs': ligne.tache_code_wbs,
            'baseline_debut': (
                ligne.date_debut_prevue.isoformat()
                if ligne.date_debut_prevue else None),
            'baseline_fin': (
                ligne.date_fin_prevue.isoformat()
                if ligne.date_fin_prevue else None),
            'baseline_charge': (
                str(ligne.charge_estimee)
                if ligne.charge_estimee is not None else None),
            'reel_debut': reel_debut.isoformat() if reel_debut else None,
            'reel_fin': reel_fin.isoformat() if reel_fin else None,
            'reel_charge': (
                str(reel_charge) if reel_charge is not None else None),
            'ecart_debut_jours': ecart_debut,
            'ecart_fin_jours': ecart_fin,
            'derive_charge': derive_charge,
            'tache_supprimee': tache is None,
        })
    return {
        'baseline': baseline.id,
        'projet': baseline.projet_id,
        'glissement_max_fin': glissement_max,
        'lignes': lignes,
    }


def calendrier_de_projet(projet):
    """Calendrier ouvré d'un projet (ou None s'il n'en a pas) — lecture seule."""
    return CalendrierProjet.objects.filter(
        projet=projet, company=projet.company).first()


def _jours_ouvres_et_feries(projet):
    """(set d'indices ouvrés, set de dates fériées) du calendrier — défaut L–V.

    Sans calendrier configuré : lundi→vendredi ouvrés, aucun férié.
    """
    cal = calendrier_de_projet(projet)
    if cal is None:
        return {0, 1, 2, 3, 4}, set()
    feries = set(cal.jours_feries.values_list('date', flat=True))
    return set(cal.jours_ouvres()), feries


def est_jour_ouvre(projet, jour):
    """True si ``jour`` (date) est OUVRÉ selon le calendrier du projet."""
    ouvres, feries = _jours_ouvres_et_feries(projet)
    return jour.weekday() in ouvres and jour not in feries


def jours_ouvres_entre(projet, debut, fin):
    """Nombre de jours OUVRÉS dans l'intervalle [debut, fin) (fin exclusive).

    Lecture seule. Respecte les week-ends définis par le calendrier du projet et
    ses jours fériés. ``debut``/``fin`` sont des dates ; renvoie 0 si
    ``fin <= debut``.
    """
    if fin <= debut:
        return 0
    ouvres, feries = _jours_ouvres_et_feries(projet)
    n = 0
    cur = debut
    while cur < fin:
        if cur.weekday() in ouvres and cur not in feries:
            n += 1
        cur += timedelta(days=1)
    return n


def ajouter_jours_ouvres(projet, debut, n_jours_ouvres):
    """Date obtenue en ajoutant ``n_jours_ouvres`` jours OUVRÉS à ``debut``.

    Lecture seule. ``debut`` est inclus s'il est ouvré : ajouter 0 jour ouvré
    renvoie le premier jour ouvré ≥ ``debut``. Respecte week-ends et fériés du
    calendrier projet. Sert à projeter une durée en jours ouvrés sur le
    calendrier (raffinement de la projection naïve du Gantt PROJ10).
    """
    ouvres, feries = _jours_ouvres_et_feries(projet)

    def _ouvre(d):
        return d.weekday() in ouvres and d not in feries

    cur = debut
    while not _ouvre(cur):
        cur += timedelta(days=1)
    restants = n_jours_ouvres
    while restants > 0:
        cur += timedelta(days=1)
        if _ouvre(cur):
            restants -= 1
    return cur


def chemin_critique(projet):
    """Calcul du chemin critique (CPM) + marges d'un projet (lecture seule).

    Délègue à ``cpm.calculer_cpm`` (import local pour éviter tout cycle). Renvoie
    un dict ``{duree_projet, has_cycle, chemin_critique, taches}`` — voir
    ``cpm.calculer_cpm``. La société est portée par le projet.
    """
    from . import cpm
    return cpm.calculer_cpm(projet)


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


def _poids_tache(tache):
    """Poids d'une tâche pour le roll-up — sa ``charge_estimee`` (≥ 0).

    Une charge absente ou nulle vaut 0 : la pondération retombe alors sur une
    moyenne ÉGALE entre fratries (voir ``_rollup_node``).
    """
    charge = tache.charge_estimee
    if charge is None:
        return 0.0
    return max(0.0, float(charge))


def _rollup_node(tache, enfants_par_parent):
    """Roll-up RÉCURSIF de l'avancement d'une tâche pondéré par charge.

    Une tâche FEUILLE porte son ``avancement_pct`` propre et son poids =
    ``charge_estimee`` (ou 0). Une tâche PARENTE voit son avancement RECALCULÉ
    comme la moyenne des avancements de ses enfants pondérée par leur charge
    cumulée ; si la charge cumulée des enfants est nulle, on retombe sur une
    moyenne ÉGALE (chaque enfant compte pour 1). Renvoie un dict
    ``{id, libelle, code_wbs, charge, avancement_pct, est_feuille, sous_taches}``
    où ``avancement_pct`` est la valeur ROLLÉE (arrondie à l'entier) et
    ``charge`` la charge cumulée de la branche (somme des charges des feuilles,
    au minimum la charge propre des feuilles).
    """
    enfants = enfants_par_parent.get(tache.id, [])
    if not enfants:
        poids = _poids_tache(tache)
        return {
            'id': tache.id,
            'libelle': tache.libelle,
            'code_wbs': tache.code_wbs,
            'charge': poids,
            'avancement_pct': int(tache.avancement_pct),
            'est_feuille': True,
            'sous_taches': [],
        }
    sous = [_rollup_node(child, enfants_par_parent) for child in enfants]
    charge_cumulee = sum(n['charge'] for n in sous)
    if charge_cumulee > 0:
        total = sum(n['avancement_pct'] * n['charge'] for n in sous)
        avancement = total / charge_cumulee
    else:
        # Aucune charge sur la branche : moyenne ÉGALE entre enfants.
        avancement = sum(n['avancement_pct'] for n in sous) / len(sous)
    return {
        'id': tache.id,
        'libelle': tache.libelle,
        'code_wbs': tache.code_wbs,
        'charge': charge_cumulee,
        'avancement_pct': int(round(avancement)),
        'est_feuille': False,
        'sous_taches': sous,
    }


def rollup_avancement(projet):
    """Roll-up d'avancement pondéré par charge d'un projet (lecture seule).

    Renvoie ``{avancement_pct, charge_totale, taches}`` où ``taches`` est
    l'arborescence WBS avec, sur chaque nœud parent, l'avancement RECALCULÉ
    comme moyenne pondérée par la charge de ses enfants (PROJ9). L'avancement
    GLOBAL du projet est le roll-up de ses tâches RACINES (mêmes règles de
    pondération). Une seule requête : on charge toutes les tâches puis on
    déroule la récursion en mémoire. Ne MODIFIE aucune donnée.
    """
    taches = list(taches_for_projet(projet))
    enfants_par_parent = {}
    for tache in taches:
        enfants_par_parent.setdefault(tache.parent_id, []).append(tache)
    racines = enfants_par_parent.get(None, [])
    arbre = [_rollup_node(racine, enfants_par_parent) for racine in racines]
    charge_totale = sum(n['charge'] for n in arbre)
    if charge_totale > 0:
        avancement = sum(
            n['avancement_pct'] * n['charge'] for n in arbre) / charge_totale
    elif arbre:
        avancement = sum(n['avancement_pct'] for n in arbre) / len(arbre)
    else:
        avancement = 0
    return {
        'avancement_pct': int(round(avancement)),
        'charge_totale': charge_totale,
        'taches': arbre,
    }


def planning_gantt(projet):
    """Planning Gantt d'un projet (lecture seule) — barres + liens de dépendance.

    Délègue à ``gantt.construire_planning`` (import local anti-cycle). Renvoie
    ``{date_origine, duree_projet, taches: [...], liens: [...]}`` — voir
    ``gantt.construire_planning``. La société est portée par le projet.
    """
    from . import gantt
    return gantt.construire_planning(projet)


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


# ── PROJ14 : Détection des retards (tâches/jalons à risque) ──────────────────

# Seuil par défaut (en jours) : une tâche/un jalon est « à risque » si sa date
# de fin prévue tombe dans les N prochains jours (aujourd'hui inclu).
_SEUIL_RISQUE_DEFAUT = 7


def _risque_tache(tache, aujourd_hui, seuil_jours):
    """Niveau de risque d'une tâche (lecture seule, sans IO).

    Renvoie :
      - ``'en_retard'`` : date de fin prévue DÉPASSÉE et tâche non terminée
      - ``'a_risque'``  : date de fin prévue dans [aujourd'hui, +seuil_jours] et
                          tâche non terminée (statut ≠ 'termine')
      - None            : dans les délais ou tâche terminée / sans date de fin

    Le statut ``'termine'`` est la seule valeur excluant la tâche du radar ;
    ``'bloque'`` + ``'en_cours'`` sont considérés normalement.
    """
    if tache.statut == Tache.Statut.TERMINE:
        return None
    fin = tache.date_fin_prevue
    if fin is None:
        return None
    if fin < aujourd_hui:
        return 'en_retard'
    if fin <= aujourd_hui + timedelta(days=seuil_jours):
        return 'a_risque'
    return None


def _risque_jalon(jalon, aujourd_hui, seuil_jours):
    """Niveau de risque d'un jalon (lecture seule, sans IO).

    Renvoie :
      - ``'en_retard'`` : date prévue DÉPASSÉE et jalon non atteint
      - ``'a_risque'``  : date prévue dans [aujourd'hui, +seuil_jours] et jalon
                          non atteint (statut ≠ 'atteint')
      - None            : dans les délais, atteint, ou manqué déjà comptabilisé

    ``'manque'`` (Jalon.Statut.MANQUE) est un état terminal de RATAGE déjà
    enregistré manuellement par l'utilisateur : il reste dans ``'en_retard'``
    sauf s'il a une ``date_reelle`` prouvant qu'il a été soldé (auquel cas on
    traite comme atteint). En pratique un jalon MANQUÉ est déjà un retard connu.
    """
    if jalon.statut == Jalon.Statut.ATTEINT:
        return None
    date_prevue = jalon.date_prevue
    if date_prevue < aujourd_hui:
        return 'en_retard'
    if date_prevue <= aujourd_hui + timedelta(days=seuil_jours):
        return 'a_risque'
    return None


def retards_projet(projet, seuil_jours=None):
    """Tâches et jalons EN RETARD ou À RISQUE d'un projet (lecture seule).

    Compare les dates de fin prévues au jour courant (``datetime.date.today()``).
    Le ``seuil_jours`` (par défaut :attr:`_SEUIL_RISQUE_DEFAUT`) définit
    l'horizon « à risque » : une tâche/un jalon dont la fin prévue tombe dans
    les N prochains jours est « à risque » (pas encore en retard mais proche).

    Renvoie un dict ::

        {
          "date_reference": "YYYY-MM-DD",   # aujourd'hui (ISO)
          "seuil_jours": 7,
          "taches_en_retard":  [...],        # statut == 'en_retard'
          "taches_a_risque":   [...],        # statut == 'a_risque'
          "jalons_en_retard":  [...],
          "jalons_a_risque":   [...],
          "nb_taches_en_retard":  int,
          "nb_taches_a_risque":   int,
          "nb_jalons_en_retard":  int,
          "nb_jalons_a_risque":   int,
        }

    Chaque entrée tâche ::

        {
          "id": int, "libelle": str, "code_wbs": str, "statut": str,
          "avancement_pct": int,
          "date_fin_prevue": "YYYY-MM-DD",
          "retard_jours": int,   # positif = retard en jours par rapport à aujourd'hui
                                 # négatif = encore N jours avant l'échéance
          "phase": int | null, "parent": int | null,
        }

    Chaque entrée jalon ::

        {
          "id": int, "libelle": str, "statut": str,
          "date_prevue": "YYYY-MM-DD",
          "retard_jours": int,
          "facturation_pct": str,
          "phase": int | null, "tache": int | null,
        }

    Seules les tâches de PREMIER niveau ou de sous-tâche (toutes profondeurs)
    ayant une ``date_fin_prevue`` sont analysées. Les tâches terminées
    (``statut == 'termine'``) et les jalons atteints (``statut == 'atteint'``)
    sont EXCLUS du radar. La société est portée par le projet (le filtre est
    appliqué par les sélecteurs ``taches_for_projet`` / ``jalons_for_projet``).
    """
    if seuil_jours is None:
        seuil_jours = _SEUIL_RISQUE_DEFAUT
    aujourd_hui = _date.today()

    taches_retard = []
    taches_risque = []
    for tache in taches_for_projet(projet):
        niveau = _risque_tache(tache, aujourd_hui, seuil_jours)
        if niveau is None:
            continue
        fin = tache.date_fin_prevue
        retard_jours = (aujourd_hui - fin).days  # >0 = retard, <0 = jours restants
        item = {
            'id': tache.id,
            'libelle': tache.libelle,
            'code_wbs': tache.code_wbs,
            'statut': tache.statut,
            'avancement_pct': tache.avancement_pct,
            'date_fin_prevue': fin.isoformat(),
            'retard_jours': retard_jours,
            'phase': tache.phase_id,
            'parent': tache.parent_id,
        }
        if niveau == 'en_retard':
            taches_retard.append(item)
        else:
            taches_risque.append(item)

    jalons_retard = []
    jalons_risque = []
    for jalon in jalons_for_projet(projet):
        niveau = _risque_jalon(jalon, aujourd_hui, seuil_jours)
        if niveau is None:
            continue
        date_prevue = jalon.date_prevue
        retard_jours = (aujourd_hui - date_prevue).days
        item = {
            'id': jalon.id,
            'libelle': jalon.libelle,
            'statut': jalon.statut,
            'date_prevue': date_prevue.isoformat(),
            'retard_jours': retard_jours,
            'facturation_pct': str(jalon.facturation_pct),
            'phase': jalon.phase_id,
            'tache': jalon.tache_id,
        }
        if niveau == 'en_retard':
            jalons_retard.append(item)
        else:
            jalons_risque.append(item)

    return {
        'date_reference': aujourd_hui.isoformat(),
        'seuil_jours': seuil_jours,
        'taches_en_retard': taches_retard,
        'taches_a_risque': taches_risque,
        'jalons_en_retard': jalons_retard,
        'jalons_a_risque': jalons_risque,
        'nb_taches_en_retard': len(taches_retard),
        'nb_taches_a_risque': len(taches_risque),
        'nb_jalons_en_retard': len(jalons_retard),
        'nb_jalons_a_risque': len(jalons_risque),
    }


# ── PROJ17 : Indisponibilités ressources (congé/formation/arrêt) ─────────────


def indisponibilites_de_ressource(ressource):
    """Indisponibilités d'une ressource (QuerySet scopé société, par date).

    Lecture seule. La société est portée par la ressource ; on filtre aussi sur
    ``ressource.company`` par sécurité même si le FK ``ressource`` la garantit.
    Ordre : ``date_debut`` croissante puis ``id``.
    """
    return Indisponibilite.objects.filter(
        ressource=ressource, company=ressource.company,
    ).order_by('date_debut', 'id')


def indisponibilites_sur_periode(ressource, debut, fin):
    """Indisponibilités d'une ressource CHEVAUCHANT la fenêtre [debut, fin].

    Lecture seule. Bornes INCLUSIVES des deux côtés : une indisponibilité
    chevauche la fenêtre dès que ``date_debut <= fin`` ET ``date_fin >= debut``.
    QuerySet scopé société.
    """
    return indisponibilites_de_ressource(ressource).filter(
        date_debut__lte=fin, date_fin__gte=debut)


def ressource_disponible_sur_periode(ressource, debut, fin):
    """True si la ressource est DISPONIBLE sur toute la fenêtre [debut, fin].

    Lecture seule. La ressource est INDISPONIBLE dès qu'une indisponibilité
    (congé/formation/arrêt) chevauche la fenêtre (bornes inclusives). Sert à la
    planification / l'affectation (PROJ16/18/19) pour exclure une ressource
    indisponible. La société est portée par la ressource.
    """
    return not indisponibilites_sur_periode(ressource, debut, fin).exists()


# ── PROJ18 : Plan de charge (capacité vs affecté) ────────────────────────────

# Semaine ouvrée par défaut du plan de charge : lundi→vendredi. Le plan de
# charge est TRANSVERSAL (à l'échelle société, toutes ressources confondues) et
# n'est donc pas rattaché au calendrier d'UN projet (relation 1-1 projet) — on
# applique une semaine standard L-V, indépendante de tout CalendrierProjet.
_JOURS_OUVRES_DEFAUT = frozenset({0, 1, 2, 3, 4})
# Heures travaillées par jour ouvré (capacité d'une ressource à plein temps) —
# valeur de repli quand la société n'a PAS ENCORE de ``ReglageTemps`` (ZPRJ1).
_HEURES_PAR_JOUR_DEFAUT = 8


def _heures_par_jour_reglage(company):
    """``heures_par_jour`` du ``ReglageTemps`` de ``company`` (ZPRJ1), LECTURE
    SEULE : ``_HEURES_PAR_JOUR_DEFAUT`` (8) si aucun réglage n'existe encore
    pour la société (jamais de création depuis un sélecteur)."""
    from .models import ReglageTemps

    reglage = ReglageTemps.objects.filter(company=company).first()
    if reglage is None:
        return _HEURES_PAR_JOUR_DEFAUT
    return reglage.heures_par_jour


def _jours_ouvres_periode(debut, fin, jours_ouvres):
    """Nombre de jours OUVRÉS dans [debut, fin] — bornes INCLUSIVES des 2 côtés.

    Lecture seule. Contrairement à ``jours_ouvres_entre`` (fin exclusive, liée à
    un projet), cette aide compte une fenêtre inclusive avec une semaine ouvrée
    explicite — la convention des affectations / indisponibilités (PROJ16/17).
    Renvoie 0 si ``fin < debut``.
    """
    if fin < debut:
        return 0
    n = 0
    cur = debut
    while cur <= fin:
        if cur.weekday() in jours_ouvres:
            n += 1
        cur += timedelta(days=1)
    return n


def _chevauchement_inclusif(a_debut, a_fin, b_debut, b_fin):
    """Fenêtre [max(débuts), min(fins)] de chevauchement, ou ``None`` si disjoint.

    Bornes INCLUSIVES (convention PROJ16/17). Renvoie ``(debut, fin)`` du
    recouvrement quand les deux intervalles se chevauchent, sinon ``None``.
    """
    debut = a_debut if a_debut > b_debut else b_debut
    fin = a_fin if a_fin < b_fin else b_fin
    if fin < debut:
        return None
    return debut, fin


def _charge_affectee_periode(affectation, debut, fin, jours_ouvres):
    """Heures AFFECTÉES par une affectation tombant dans [debut, fin] (inclusif).

    Lecture seule. La charge stockée (``charge_jours``, en jours-homme) est
    convertie en heures (× heures/jour) puis PRORATÉE par la fraction de jours
    OUVRÉS de l'affectation qui tombe dans la fenêtre :

        heures = charge_jours × heures_par_jour × (j-ouvrés_dans_fenêtre /
                                                   j-ouvrés_de_l'affectation)

    Si l'affectation n'a aucun jour ouvré (week-end intégral) le prorata vaut 0
    (jamais de division par zéro). ``charge_jours`` nul/None → 0.
    """
    if affectation.charge_jours is None:
        return 0.0
    chevauchement = _chevauchement_inclusif(
        affectation.date_debut, affectation.date_fin, debut, fin)
    if chevauchement is None:
        return 0.0
    jours_affectation = _jours_ouvres_periode(
        affectation.date_debut, affectation.date_fin, jours_ouvres)
    if jours_affectation <= 0:
        return 0.0
    jours_fenetre = _jours_ouvres_periode(
        chevauchement[0], chevauchement[1], jours_ouvres)
    fraction = jours_fenetre / jours_affectation
    return float(affectation.charge_jours) * _HEURES_PAR_JOUR_DEFAUT * fraction


def plan_de_charge(company, debut, fin, heures_par_jour=None,
                   ressource_id=None):
    """Plan de charge d'une société sur [debut, fin] : capacité vs affecté.

    PROJ18 — pour CHAQUE ``RessourceProfil`` ACTIVE de la société (ou la seule
    ``ressource_id`` demandée), agrège :

    * ``capacite_heures`` — jours OUVRÉS (semaine L-V par défaut) de la fenêtre
      INCLUSIVE [debut, fin], MOINS les jours ouvrés couverts par une
      indisponibilité (congé/formation/arrêt) chevauchant la fenêtre, × le
      nombre d'heures par jour ouvré (``heures_par_jour`` — défaut : le
      réglage ``heures_par_jour`` de ``ReglageTemps`` de la société, ZPRJ1,
      lui-même par défaut 8) ;
    * ``affecte_heures`` — somme PRORATÉE des affectations (PROJ16) de la
      ressource — directes (``ressource``) ET via une ``Equipe`` dont elle est
      membre (la charge d'équipe est répartie à parts ÉGALES entre ses membres
      du moment) — dont la période chevauche la fenêtre, chaque affectation
      étant proratée par sa fraction de jours ouvrés tombant dans [debut, fin] ;
    * ``surcharge`` — booléen ``affecte_heures > capacite_heures`` ;
    * ``utilisation_pct`` — ``affecte / capacite × 100`` arrondi, ou ``None``
      quand la capacité est nulle (GARDE division par zéro — une ressource sans
      capacité mais avec une charge reste signalée ``surcharge=True``).

    Lecture seule, multi-société : seules les données ``company`` sont lues
    (affectations, indisponibilités et membres d'équipe sont tous filtrés sur la
    même société). ``debut``/``fin`` sont des dates ; ``fin < debut`` → fenêtre
    vide (toutes capacités 0). Les actifs matériels et les affectations sans
    ``charge_jours`` n'entrent pas dans l'affecté. Renvoie un dict
    ``{debut, fin, heures_par_jour, lignes: [...], nb_surcharges}`` trié par nom
    de ressource.
    """
    if heures_par_jour is None:
        heures_par_jour = _heures_par_jour_reglage(company)
    try:
        heures_jour = float(heures_par_jour)
    except (TypeError, ValueError):
        heures_jour = float(_HEURES_PAR_JOUR_DEFAUT)
    if heures_jour < 0:
        heures_jour = 0.0
    jours_ouvres = _JOURS_OUVRES_DEFAUT

    ressources = RessourceProfil.objects.filter(company=company, actif=True)
    if ressource_id is not None:
        ressources = ressources.filter(id=ressource_id)
    ressources = list(ressources.order_by('nom', 'id'))

    # Map ressource_id -> ids des équipes (même société) dont elle est membre.
    equipes_par_ressource = {}
    equipes_qs = Equipe.objects.filter(company=company).prefetch_related(
        'membres')
    membres_par_equipe = {}
    for equipe in equipes_qs:
        membres = [m for m in equipe.membres.all() if m.actif]
        membres_par_equipe[equipe.id] = membres
        for membre in membres:
            equipes_par_ressource.setdefault(membre.id, set()).add(equipe.id)

    # Affectations société chevauchant la fenêtre, avec une charge renseignée.
    affectations = list(
        AffectationRessource.objects.filter(
            company=company,
            charge_jours__isnull=False,
            date_debut__lte=fin,
            date_fin__gte=debut,
        ).select_related('ressource', 'equipe'))

    lignes = []
    nb_surcharges = 0
    for ressource in ressources:
        capacite_brute = _jours_ouvres_periode(debut, fin, jours_ouvres)
        # Retrancher les jours ouvrés couverts par une indisponibilité.
        jours_indispo = 0
        for indispo in indisponibilites_sur_periode(ressource, debut, fin):
            chev = _chevauchement_inclusif(
                indispo.date_debut, indispo.date_fin, debut, fin)
            if chev is not None:
                jours_indispo += _jours_ouvres_periode(
                    chev[0], chev[1], jours_ouvres)
        jours_dispo = capacite_brute - jours_indispo
        if jours_dispo < 0:
            jours_dispo = 0
        capacite_heures = jours_dispo * heures_jour

        affecte_heures = 0.0
        equipe_ids = equipes_par_ressource.get(ressource.id, set())
        for aff in affectations:
            heures = 0.0
            if aff.ressource_id == ressource.id:
                heures = _charge_affectee_periode(
                    aff, debut, fin, jours_ouvres)
            elif aff.equipe_id in equipe_ids:
                membres = membres_par_equipe.get(aff.equipe_id, [])
                n_membres = len(membres)
                if n_membres > 0:
                    heures = _charge_affectee_periode(
                        aff, debut, fin, jours_ouvres) / n_membres
            affecte_heures += heures

        surcharge = affecte_heures > capacite_heures
        if surcharge:
            nb_surcharges += 1
        if capacite_heures > 0:
            utilisation_pct = round(affecte_heures / capacite_heures * 100, 1)
        else:
            utilisation_pct = None

        # ZPRJ2 — statut de publication des affectations DIRECTES de la
        # ressource (les affectations d'équipe ne portent pas d'individu à
        # publier ici — elles restent visibles sur la ligne de l'équipe).
        affectations_ressource = [
            {
                'id': aff.id, 'tache_id': aff.tache_id,
                'date_debut': aff.date_debut.isoformat(),
                'date_fin': aff.date_fin.isoformat(),
                'statut_publication': aff.statut_publication,
            }
            for aff in affectations if aff.ressource_id == ressource.id
        ]

        lignes.append({
            'ressource': ressource.id,
            'nom': ressource.nom,
            'role': ressource.role,
            'capacite_heures': round(capacite_heures, 2),
            'affecte_heures': round(affecte_heures, 2),
            'disponible_heures': round(capacite_heures - affecte_heures, 2),
            'jours_ouvres': capacite_brute,
            'jours_indispo': jours_indispo,
            'utilisation_pct': utilisation_pct,
            'surcharge': surcharge,
            'affectations': affectations_ressource,
        })

    return {
        'debut': debut.isoformat(),
        'fin': fin.isoformat(),
        'heures_par_jour': heures_jour,
        'nb_surcharges': nb_surcharges,
        'lignes': lignes,
    }


# ── PROJ19 : Détection de conflits d'affectation ─────────────────────────────


def _affectation_dict(aff):
    """Dict d'affichage minimal d'une ``AffectationRessource`` (lecture seule).

    Porte la tâche, le projet (via la tâche, préchargé) et la fenêtre. Ne lit
    aucune donnée d'une AUTRE société : l'appelant ne passe que des affectations
    déjà scopées société.
    """
    tache = aff.tache
    return {
        'affectation': aff.id,
        'tache': aff.tache_id,
        'tache_libelle': tache.libelle if tache else '',
        'projet': tache.projet_id if tache else None,
        'date_debut': aff.date_debut.isoformat(),
        'date_fin': aff.date_fin.isoformat(),
        'charge_jours': (
            str(aff.charge_jours) if aff.charge_jours is not None else None),
    }


def _paires_en_conflit(affectations):
    """Couples d'affectations dont les fenêtres se CHEVAUCHENT (bornes inclusives).

    ``affectations`` est une liste d'``AffectationRessource`` d'UNE même
    ressource. On trie par ``date_debut`` puis on compare chaque affectation aux
    suivantes tant qu'elles peuvent encore chevaucher (balayage trié). Deux
    fenêtres se chevauchent dès que ``a.date_debut <= b.date_fin`` ET
    ``a.date_fin >= b.date_debut`` (convention PROJ16/17, bornes inclusives des
    deux côtés). Renvoie une liste de couples ``(aff_a, aff_b)`` avec
    ``aff_a`` la plus précoce. Une seule affectation → aucune paire.
    """
    ordonnees = sorted(affectations, key=lambda a: (a.date_debut, a.date_fin,
                                                    a.id))
    paires = []
    n = len(ordonnees)
    for i in range(n):
        a = ordonnees[i]
        for j in range(i + 1, n):
            b = ordonnees[j]
            # Liste triée par date_debut : dès que b démarre après la fin de a,
            # aucune affectation suivante ne peut plus chevaucher a (elles
            # démarrent encore plus tard) → on coupe la boucle interne.
            if b.date_debut > a.date_fin:
                break
            # a.date_debut <= b.date_debut garanti par le tri ; il reste à
            # vérifier le chevauchement inclusif (équivaut à b.date_debut <=
            # a.date_fin ici, déjà impliqué par l'absence de break).
            if a.date_debut <= b.date_fin and a.date_fin >= b.date_debut:
                paires.append((a, b))
    return paires


def conflits_affectation(company, debut, fin):
    """Conflits de double-affectation d'une société sur [debut, fin] (PROJ19).

    Détecte, pour CHAQUE ``RessourceProfil`` de la société, les cas où elle est
    allouée à PLUSIEURS ``AffectationRessource`` dont les fenêtres se
    CHEVAUCHENT — c'est-à-dire une ressource double-bookée sur une même période.
    On prend en compte les affectations DIRECTES (vecteur ``ressource``) ET les
    affectations d'une ``Equipe`` dont la ressource est membre : une personne
    affectée en direct sur une tâche ET via son équipe sur une autre tâche au
    même moment est en conflit. Les affectations d'actif matériel (vecteur
    ``actif_*``) n'entrent PAS dans la détection (une ressource = une personne).

    La fenêtre [debut, fin] est INCLUSIVE des deux bornes (convention
    PROJ16/17) : seules les affectations chevauchant la fenêtre sont examinées,
    et deux d'entre elles sont en conflit dès que leurs fenêtres se chevauchent
    (peu importe qu'un week-end les sépare — la détection est calendaire, pas
    ouvrée : une affectation reste une réservation continue de la ressource).

    Optionnellement, chaque ligne de ressource porte aussi ses
    ``indisponibilites`` (congé/formation/arrêt) chevauchant la fenêtre, pour
    signaler une affectation posée alors que la ressource est indisponible
    (``affectations_sur_indispo``).

    Lecture seule, multi-société : seules les données ``company`` sont lues
    (affectations, équipes et indisponibilités sont toutes filtrées sur la même
    société). ``debut``/``fin`` sont des dates ; une fenêtre VIDE
    (``fin < debut``) → aucun conflit (garde explicite). Renvoie un dict ::

        {
          "debut": "YYYY-MM-DD", "fin": "YYYY-MM-DD",
          "nb_ressources_en_conflit": int,
          "nb_conflits": int,                # total de paires en conflit
          "lignes": [                        # une entrée par ressource conflictuelle
            {
              "ressource": int, "nom": str, "role": str,
              "conflits": [                  # paires d'affectations qui se chevauchent
                {
                  "affectation_a": {...}, "affectation_b": {...},
                  "chevauchement_debut": "YYYY-MM-DD",
                  "chevauchement_fin": "YYYY-MM-DD",
                  "via_equipe": bool,        # au moins un côté vient d'une équipe
                },
                ...
              ],
              "affectations_sur_indispo": [  # affectations posées sur une indispo
                {"affectation": {...}, "indispo_debut": "...",
                 "indispo_fin": "...", "type_indispo": "..."},
                ...
              ],
            },
            ...
          ],
        }
    """
    # Garde fenêtre vide : aucune affectation ne peut être en conflit.
    if fin < debut:
        return {
            'debut': debut.isoformat(),
            'fin': fin.isoformat(),
            'nb_ressources_en_conflit': 0,
            'nb_conflits': 0,
            'lignes': [],
        }

    ressources = list(
        RessourceProfil.objects.filter(company=company).order_by('nom', 'id'))

    # Map ressource_id -> ids des équipes (même société) dont elle est membre,
    # et l'inverse pour étiqueter une affectation d'équipe sur chaque membre.
    equipe_ids_par_ressource = {}
    equipes_qs = Equipe.objects.filter(company=company).prefetch_related(
        'membres')
    membres_par_equipe = {}
    for equipe in equipes_qs:
        membres = list(equipe.membres.all())
        membres_par_equipe[equipe.id] = membres
        for membre in membres:
            equipe_ids_par_ressource.setdefault(membre.id, set()).add(equipe.id)

    # Affectations société (personnes + équipes) chevauchant la fenêtre. Les
    # affectations d'actif matériel (sans ressource ni équipe) sont écartées.
    affectations = list(
        AffectationRessource.objects.filter(
            company=company,
            date_debut__lte=fin,
            date_fin__gte=debut,
        ).filter(
            Q(ressource__isnull=False) | Q(equipe__isnull=False)
        ).select_related('tache'))

    # Indexer les affectations par ressource concernée (directe + via équipe).
    # ``via`` mémorise si l'affectation touche la ressource via une équipe.
    affectations_par_ressource = {}
    for aff in affectations:
        if aff.ressource_id is not None:
            affectations_par_ressource.setdefault(
                aff.ressource_id, []).append((aff, False))
        elif aff.equipe_id is not None:
            for membre in membres_par_equipe.get(aff.equipe_id, []):
                affectations_par_ressource.setdefault(
                    membre.id, []).append((aff, True))

    lignes = []
    nb_conflits = 0
    for ressource in ressources:
        entrees = affectations_par_ressource.get(ressource.id, [])
        # Index (aff_id, via) pour étiqueter chaque côté d'une paire.
        via_par_aff = {}
        affs = []
        for aff, via in entrees:
            affs.append(aff)
            # Une affectation directe prime : si la ressource y est à la fois en
            # direct et via une équipe (cas théorique), elle compte comme directe.
            via_par_aff[aff.id] = via_par_aff.get(aff.id, True) and via
        paires = _paires_en_conflit(affs)

        conflits = []
        for a, b in paires:
            chev = _chevauchement_inclusif(
                a.date_debut, a.date_fin, b.date_debut, b.date_fin)
            if chev is None:  # pragma: no cover - garanti par _paires_en_conflit
                continue
            via_equipe = bool(via_par_aff.get(a.id) or via_par_aff.get(b.id))
            conflits.append({
                'affectation_a': _affectation_dict(a),
                'affectation_b': _affectation_dict(b),
                'chevauchement_debut': chev[0].isoformat(),
                'chevauchement_fin': chev[1].isoformat(),
                'via_equipe': via_equipe,
            })

        # Affectations posées alors que la ressource est indisponible.
        sur_indispo = []
        if affs:
            indispos = list(indisponibilites_sur_periode(
                ressource, debut, fin))
            for aff in affs:
                for indispo in indispos:
                    if (aff.date_debut <= indispo.date_fin
                            and aff.date_fin >= indispo.date_debut):
                        sur_indispo.append({
                            'affectation': _affectation_dict(aff),
                            'indispo_debut': indispo.date_debut.isoformat(),
                            'indispo_fin': indispo.date_fin.isoformat(),
                            'type_indispo': indispo.type_indispo,
                        })

        if conflits or sur_indispo:
            nb_conflits += len(conflits)
            lignes.append({
                'ressource': ressource.id,
                'nom': ressource.nom,
                'role': ressource.role,
                'conflits': conflits,
                'affectations_sur_indispo': sur_indispo,
            })

    return {
        'debut': debut.isoformat(),
        'fin': fin.isoformat(),
        'nb_ressources_en_conflit': len(lignes),
        'nb_conflits': nb_conflits,
        'lignes': lignes,
    }


# ── PROJ20 : Nivellement de charge (levelling) ───────────────────────────────


def _periodes_se_chevauchent(a_debut, a_fin, b_debut, b_fin):
    """True si deux fenêtres [a_debut, a_fin] / [b_debut, b_fin] se chevauchent.

    Bornes INCLUSIVES des deux côtés (convention PROJ16/17/19) : deux fenêtres se
    chevauchent dès que ``a_debut <= b_fin`` ET ``a_fin >= b_debut``. Sert à
    garantir qu'un déplacement proposé ne crée PAS un conflit PROJ19 sur le
    destinataire (jamais une fenêtre qui en recouvre une autre déjà posée).
    """
    return a_debut <= b_fin and a_fin >= b_debut


def nivellement_charge(company, debut, fin, heures_par_jour=None):
    """Propose un rééquilibrage des ressources SUR-CHARGÉES vers les SOUS-CHARGÉES.

    PROJ20 — l'équivalent gestion-projet de FG301. S'appuie sur le plan de
    charge (PROJ18, ``plan_de_charge`` : capacité = jours ouvrés L-V moins
    indisponibilités × heures/jour ; affecté = somme proratée des affectations,
    directes ET via équipe) pour classer chaque ``RessourceProfil`` ACTIVE :

    * SUR-CHARGÉE : ``affecte_heures > capacite_heures`` (``surcharge=True``) ;
    * SOUS-CHARGÉE : ``disponible_heures = capacite − affecté > 0``.

    Pour chaque ressource sur-chargée, on examine ses affectations DIRECTES
    (vecteur ``ressource``) chevauchant la fenêtre et propose de déplacer
    celles-ci, en commençant par les plus TARDIVES (le début de fenêtre reste
    stable), vers la ressource sous-chargée qui a LE PLUS de marge restante, à
    condition que ce destinataire :

      * ait assez de marge d'heures libres pour absorber la charge proratée de
        l'affectation (sinon le déplacement re-créerait une surcharge) ;
      * n'ait AUCUNE affectation (ni proposition déjà acceptée) dont la fenêtre
        chevauche celle de l'affectation déplacée — sinon on recréerait un
        conflit PROJ19 (double-booking) sur le destinataire.

    L'état (marge restante + fenêtres occupées) est simulé EN MÉMOIRE au fil des
    propositions pour rester équitable et anti-conflit ; rien n'est écrit en
    base. Seules les affectations DIRECTES (personne) sont déplaçables : une
    affectation d'équipe ou d'actif matériel n'est jamais proposée (on ne casse
    pas une équipe, et un actif n'est pas une personne). Une affectation sans
    ``charge_jours`` n'entre pas dans l'affecté (PROJ18) mais reste déplaçable —
    sa charge proratée vaut alors 0, elle ne consomme aucune marge.

    Lecture seule, NE MUTE RIEN, scopée société (toutes les données lues sont
    filtrées sur ``company``). ``debut``/``fin`` sont des dates ; une fenêtre
    VIDE (``fin < debut``) → aucune proposition (garde explicite). Garde
    division-par-zéro / capacité nulle héritée de ``plan_de_charge``. Renvoie un
    dict PLAT ::

        {
          "debut": "YYYY-MM-DD", "fin": "YYYY-MM-DD",
          "heures_par_jour": float,
          "surcharges": [                 # ressources sur-chargées
            {"ressource": int, "nom": str, "role": str,
             "capacite_heures": float, "affecte_heures": float,
             "exces_heures": float},
            ...
          ],
          "sous_charges": [               # ressources sous-chargées (marge > 0)
            {"ressource": int, "nom": str, "role": str,
             "capacite_heures": float, "affecte_heures": float,
             "disponible_heures": float},
            ...
          ],
          "propositions": [               # déplacements suggérés
            {"affectation": int, "tache": int, "tache_libelle": str,
             "projet": int | null,
             "date_debut": "YYYY-MM-DD", "date_fin": "YYYY-MM-DD",
             "charge_heures": float,
             "de_ressource": int, "de_nom": str,
             "vers_ressource": int, "vers_nom": str},
            ...
          ],
          "totaux": {
            "nb_surcharges": int, "nb_sous_charges": int,
            "nb_propositions": int,
            "nb_non_resolues": int,       # affectations en excès sans destinataire
          },
        }
    """
    plan = plan_de_charge(
        company, debut, fin, heures_par_jour=heures_par_jour)

    base = {
        'debut': debut.isoformat(),
        'fin': fin.isoformat(),
        'heures_par_jour': plan['heures_par_jour'],
        'surcharges': [],
        'sous_charges': [],
        'propositions': [],
        'totaux': {
            'nb_surcharges': 0,
            'nb_sous_charges': 0,
            'nb_propositions': 0,
            'nb_non_resolues': 0,
        },
    }
    # Fenêtre vide → rien à niveler (le plan de charge l'a déjà neutralisée mais
    # on garde la sortie explicite et symétrique avec PROJ19).
    if fin < debut:
        return base

    jours_ouvres = _JOURS_OUVRES_DEFAUT

    # Index des lignes du plan par ressource pour classer sur/sous-chargées.
    lignes_par_ressource = {ligne['ressource']: ligne
                            for ligne in plan['lignes']}

    surcharges = []
    sous_charges = []
    for ligne in plan['lignes']:
        if ligne['surcharge']:
            surcharges.append(ligne)
        elif ligne['disponible_heures'] > 0:
            sous_charges.append(ligne)

    # Marge d'heures libres restante par destinataire sous-chargé, mutée au fil
    # des propositions pour répartir équitablement (n'écrit RIEN en base).
    marge = {ligne['ressource']: ligne['disponible_heures']
             for ligne in sous_charges}

    # Affectations DIRECTES (vecteur ressource) chevauchant la fenêtre, scopées
    # société. On charge la tâche (pour le projet/libellé) en une requête.
    affectations = list(
        AffectationRessource.objects.filter(
            company=company,
            ressource__isnull=False,
            date_debut__lte=fin,
            date_fin__gte=debut,
        ).select_related('tache'))

    # {ressource_id: [AffectationRessource, ...]} pour les sources sur-chargées
    # et {ressource_id: [(debut, fin), ...]} des fenêtres occupées de CHAQUE
    # ressource (destinataires inclus) — anti-conflit PROJ19.
    affectations_par_source = {}
    fenetres_occupees = {}
    for aff in affectations:
        affectations_par_source.setdefault(
            aff.ressource_id, []).append(aff)
        fenetres_occupees.setdefault(aff.ressource_id, []).append(
            (aff.date_debut, aff.date_fin))

    propositions = []
    nb_non_resolues = 0

    # Traiter les sources les plus sur-chargées d'abord (excès décroissant).
    surcharges_triees = sorted(
        surcharges,
        key=lambda s: (-(s['affecte_heures'] - s['capacite_heures']),
                       s['nom'].lower(), s['ressource']))

    for source in surcharges_triees:
        src_id = source['ressource']
        # Heures à dégager pour ramener la source sous sa capacité.
        a_degager = source['affecte_heures'] - source['capacite_heures']
        if a_degager <= 0:
            continue
        candidats = affectations_par_source.get(src_id, [])
        # Déplacer en priorité les affectations les plus TARDIVES (garde le
        # début de fenêtre stable) ; tri déterministe par début puis id.
        candidats = sorted(
            candidats, key=lambda a: (a.date_debut, a.id), reverse=True)
        degage = 0.0
        for aff in candidats:
            if degage >= a_degager:
                break
            charge_h = _charge_affectee_periode(
                aff, debut, fin, jours_ouvres)
            # Destinataire : sous-chargé, marge suffisante, pas la source, pas
            # de chevauchement de fenêtre (anti-conflit PROJ19). On choisit la
            # plus grande marge restante (répartition équilibrée).
            meilleur = None
            meilleure_marge = 0.0
            for dest_id, m in marge.items():
                if dest_id == src_id:
                    continue
                if m < charge_h:
                    continue
                # Le destinataire ne doit avoir AUCUNE fenêtre qui chevauche
                # celle de l'affectation déplacée (sinon nouveau conflit PROJ19).
                conflit = False
                for (od, of_) in fenetres_occupees.get(dest_id, []):
                    if _periodes_se_chevauchent(
                            aff.date_debut, aff.date_fin, od, of_):
                        conflit = True
                        break
                if conflit:
                    continue
                if m > meilleure_marge:
                    meilleure_marge = m
                    meilleur = dest_id
            if meilleur is None:
                nb_non_resolues += 1
                continue
            tache = aff.tache
            propositions.append({
                'affectation': aff.id,
                'tache': aff.tache_id,
                'tache_libelle': tache.libelle if tache else '',
                'projet': tache.projet_id if tache else None,
                'date_debut': aff.date_debut.isoformat(),
                'date_fin': aff.date_fin.isoformat(),
                'charge_heures': round(charge_h, 2),
                'de_ressource': src_id,
                'de_nom': source['nom'],
                'vers_ressource': meilleur,
                'vers_nom': lignes_par_ressource[meilleur]['nom'],
            })
            # Met à jour l'état simulé pour les propositions suivantes (équité +
            # anti-conflit) — n'écrit RIEN en base. Le destinataire « occupe »
            # désormais la fenêtre déplacée.
            marge[meilleur] -= charge_h
            fenetres_occupees.setdefault(meilleur, []).append(
                (aff.date_debut, aff.date_fin))
            degage += charge_h

    surcharges_out = [{
        'ressource': s['ressource'],
        'nom': s['nom'],
        'role': s['role'],
        'capacite_heures': s['capacite_heures'],
        'affecte_heures': s['affecte_heures'],
        'exces_heures': round(s['affecte_heures'] - s['capacite_heures'], 2),
    } for s in surcharges_triees]

    sous_charges_out = [{
        'ressource': s['ressource'],
        'nom': s['nom'],
        'role': s['role'],
        'capacite_heures': s['capacite_heures'],
        'affecte_heures': s['affecte_heures'],
        'disponible_heures': s['disponible_heures'],
    } for s in sous_charges]

    propositions.sort(key=lambda p: (p['date_debut'], p['de_nom'].lower(),
                                     p['affectation']))

    base['surcharges'] = surcharges_out
    base['sous_charges'] = sous_charges_out
    base['propositions'] = propositions
    base['totaux'] = {
        'nb_surcharges': len(surcharges_out),
        'nb_sous_charges': len(sous_charges_out),
        'nb_propositions': len(propositions),
        'nb_non_resolues': nb_non_resolues,
    }
    return base


# ── PROJ22 : Coûts engagés/réels vs budget prévisionnel (PROJ21) ─────────────

# Types de ``ProjetLien`` qui matérialisent une dépense engagée (facture
# fournisseur / achat). Ils alimentent — quand un montant est disponible — le
# réel des catégories « matériel » et « sous-traitance ». Aujourd'hui aucune app
# cible n'expose de sélecteur de MONTANT par projet (compta est un grand livre,
# ventes n'expose qu'une carte de devis sans montant), donc ces sources DÉGRADENT
# proprement : réel = 0 + une note, sans jamais importer un modèle d'une autre
# app (frontière cross-app, CLAUDE.md). La structure ci-dessous est prête à
# brancher un sélecteur de montant le jour où une app cible en exposera un.
_LIENS_DEPENSE = (
    ProjetLien.TypeCible.FACTURE,
    ProjetLien.TypeCible.ACHAT,
)


def budget_effectif(projet):
    """Budget de référence d'un projet pour la comparaison engagé/réel.

    Choisit le budget VALIDÉ le plus récent (version la plus haute) s'il en
    existe un ; sinon le budget le plus récent quel que soit son statut ; sinon
    ``None`` (le projet n'a aucun budget). Toujours scopé société via le projet.
    Lecture seule.
    """
    base = BudgetProjet.objects.filter(
        projet=projet, company=projet.company)
    valide = base.filter(
        statut=BudgetProjet.Statut.VALIDE).order_by('-version', '-id').first()
    if valide is not None:
        return valide
    return base.order_by('-version', '-id').first()


def _mo_reelle(projet):
    """Coût de main-d'œuvre RÉEL (interne) d'un projet, en MAD.

    Agrège les affectations de RESSOURCES (personnes/rôles) du projet :
    ``charge_jours`` (jours-homme) × ``cout_horaire`` interne du profil ×
    ``_HEURES_PAR_JOUR_DEFAUT`` (8 h/j). Données 100 % INTERNES de pilotage
    (jamais exposées au client) — aucune app externe n'est sollicitée. Une
    affectation sans ``charge_jours`` ou sans coût horaire compte 0 ; les
    affectations d'équipe ou d'actif (sans profil ressource) sont ignorées
    (pas de coût horaire porté). Renvoie un ``Decimal``.
    """
    total = Decimal('0')
    heures_jour = Decimal(_HEURES_PAR_JOUR_DEFAUT)
    affectations = AffectationRessource.objects.filter(
        company=projet.company,
        tache__projet=projet,
        ressource__isnull=False,
        charge_jours__isnull=False,
    ).select_related('ressource')
    for aff in affectations:
        charge = aff.charge_jours or Decimal('0')
        cout_horaire = (
            aff.ressource.cout_horaire
            if aff.ressource_id and aff.ressource.cout_horaire is not None
            else Decimal('0'))
        total += charge * heures_jour * cout_horaire
    # Quantize à 2 décimales : charge_jours/cout_horaire ont chacun 2 dp, leur
    # produit en a 4 → la sérialisation `str()` rendrait « 800.0000 » au lieu de
    # « 800.00 » (l'écart hérite de la même sur-précision). Aligne réel + écart.
    return total.quantize(Decimal('0.01'))


def _ecart_pct(budget_montant, reel_montant):
    """Écart en % = (budget − réel) / budget × 100, ou ``None`` si budget == 0.

    Garde anti division-par-zéro : un budget nul (catégorie non budgétée)
    renvoie ``None`` plutôt que de diviser. Renvoie un ``Decimal`` arrondi à
    deux décimales sinon.
    """
    if budget_montant is None or budget_montant == 0:
        return None
    ecart = budget_montant - reel_montant
    return (ecart / budget_montant * Decimal('100')).quantize(Decimal('0.01'))


def couts_engages_vs_reels(company, projet, budget=None):
    """Comparaison BUDGET (PROJ21) vs RÉEL/engagé par catégorie pour un projet.

    Pour CHAQUE catégorie canonique (matériel / main-d'œuvre / sous-traitance /
    divers) renvoie : le ``budget`` prévisionnel (lignes ``LigneBudgetProjet`` du
    budget de référence), le ``reel`` engagé, l'``ecart`` (budget − réel) et
    l'``ecart_pct`` (None si budget == 0 — garde division-par-zéro), plus une
    ``note`` quand une source de réel n'est pas disponible.

    SOURCES du réel (jamais d'import d'un modèle d'une autre app — frontière
    cross-app, CLAUDE.md) :
      • ``main_oeuvre`` : 100 % INTERNE — affectations de ressources du projet
        (``charge_jours`` × coût horaire interne × 8 h/j).
      • ``materiel`` / ``sous_traitance`` : factures fournisseur / achats
        rattachés via ``ProjetLien`` (type facture/achat). Aucune app cible
        n'expose aujourd'hui de sélecteur de MONTANT par projet → DÉGRADE :
        réel = 0 avec une ``note`` (nb de liens rattachés sans montant
        exploitable). Aucune exception ne remonte.
      • ``divers`` : pas de source automatique → réel = 0 avec une note.

    Le ``budget`` peut être passé explicitement ; sinon on prend
    ``budget_effectif(projet)`` (validé le plus récent, sinon le plus récent).
    Si le projet n'a AUCUN budget, tous les budgets valent 0 (et ``ecart_pct``
    est None). Tout est scopé société via le projet. Lecture seule.
    """
    if budget is None:
        budget = budget_effectif(projet)

    if budget is not None:
        agg = budget_total(budget)
        budget_par_cat = dict(agg['par_categorie'])
        budget_total_montant = agg['total']
        budget_id = budget.id
        budget_version = budget.version
        budget_statut = budget.statut
    else:
        budget_par_cat = {c: Decimal('0') for c in _BUDGET_CATEGORIES}
        budget_total_montant = Decimal('0')
        budget_id = None
        budget_version = None
        budget_statut = None

    # Liens de dépense (facture/achat) rattachés au projet : on compte combien
    # sont rattachés (le montant n'est pas exploitable aujourd'hui → note).
    nb_liens_depense = ProjetLien.objects.filter(
        projet=projet, company=projet.company,
        type_cible__in=_LIENS_DEPENSE).count()

    # Réel par catégorie.
    reel_par_cat = {c: Decimal('0') for c in _BUDGET_CATEGORIES}
    notes_par_cat = {c: '' for c in _BUDGET_CATEGORIES}

    # main_oeuvre : source interne disponible (affectations × coût horaire).
    reel_par_cat[LigneBudgetProjet.Categorie.MAIN_OEUVRE] = _mo_reelle(projet)

    # materiel / sous_traitance : factures fournisseur/achats — pas de montant
    # exploitable aujourd'hui → réel reste 0 + note si des liens existent.
    if nb_liens_depense:
        note_liens = (
            f"{nb_liens_depense} facture(s)/achat(s) rattaché(s) : montant "
            "non disponible (aucun sélecteur cross-app) — réel à 0.")
        notes_par_cat[LigneBudgetProjet.Categorie.MATERIEL] = note_liens
        notes_par_cat[LigneBudgetProjet.Categorie.SOUS_TRAITANCE] = note_liens
    else:
        note_aucun = "Aucune facture/achat rattaché — réel à 0."
        notes_par_cat[LigneBudgetProjet.Categorie.MATERIEL] = note_aucun
        notes_par_cat[LigneBudgetProjet.Categorie.SOUS_TRAITANCE] = note_aucun

    # divers : pas de source automatique.
    notes_par_cat[LigneBudgetProjet.Categorie.DIVERS] = (
        "Pas de source automatique — réel à 0.")

    par_categorie = []
    reel_total_montant = Decimal('0')
    for cat in _BUDGET_CATEGORIES:
        budget_montant = budget_par_cat.get(cat, Decimal('0'))
        reel_montant = reel_par_cat.get(cat, Decimal('0'))
        reel_total_montant += reel_montant
        par_categorie.append({
            'categorie': cat,
            'budget': budget_montant,
            'reel': reel_montant,
            'ecart': budget_montant - reel_montant,
            'ecart_pct': _ecart_pct(budget_montant, reel_montant),
            'note': notes_par_cat.get(cat, ''),
        })

    return {
        'budget_id': budget_id,
        'budget_version': budget_version,
        'budget_statut': budget_statut,
        'nb_liens_depense': nb_liens_depense,
        'par_categorie': par_categorie,
        'total': {
            'budget': budget_total_montant,
            'reel': reel_total_montant,
            'ecart': budget_total_montant - reel_total_montant,
            'ecart_pct': _ecart_pct(
                budget_total_montant, reel_total_montant),
        },
    }


# ── Budget projet (PROJ21) ───────────────────────────────────────────────────
_BUDGET_CATEGORIES = [
    LigneBudgetProjet.Categorie.MATERIEL,
    LigneBudgetProjet.Categorie.MAIN_OEUVRE,
    LigneBudgetProjet.Categorie.SOUS_TRAITANCE,
    LigneBudgetProjet.Categorie.DIVERS,
]


def budget_total(budget):
    """Total prévisionnel d'un ``BudgetProjet`` ventilé par catégorie.

    Renvoie un dict ``{'total': Decimal, 'par_categorie': {cat: Decimal, ...},
    'nb_lignes': int}`` — la somme des ``montant_prevu`` des lignes du budget
    (scopées société). Toutes les catégories canoniques sont TOUJOURS présentes
    (à ``0`` si aucune ligne) ; le calcul ne divise jamais (pas de garde
    division-par-zéro nécessaire) et un budget sans ligne renvoie ``0``.
    """
    par_categorie = {c: Decimal('0') for c in _BUDGET_CATEGORIES}
    total = Decimal('0')
    nb_lignes = 0
    lignes = LigneBudgetProjet.objects.filter(
        budget=budget, company=budget.company).only('categorie', 'montant_prevu')
    for ligne in lignes:
        montant = ligne.montant_prevu or Decimal('0')
        total += montant
        par_categorie[ligne.categorie] = (
            par_categorie.get(ligne.categorie, Decimal('0')) + montant)
        nb_lignes += 1
    return {
        'total': total,
        'par_categorie': par_categorie,
        'nb_lignes': nb_lignes,
    }


# ── Alertes de dépassement budgétaire (PROJ23) ───────────────────────────────
def alertes_depassement_budgetaire(company, projet, seuil_pct=None):
    """Alertes de DÉPASSEMENT budgétaire d'un projet (PROJ23).

    S'appuie sur ``couts_engages_vs_reels`` (PROJ22 — budget PROJ21 vs réel) :
    pour CHAQUE catégorie budgétée (matériel / main-d'œuvre / sous-traitance /
    divers) et pour le TOTAL, lève une alerte quand le réel consommé approche ou
    dépasse le budget prévisionnel.

    ``seuil_pct`` (0–100, défaut 90) est le seuil d'ALERTE de consommation : à
    partir de ``seuil_pct`` % de consommation du budget, l'élément est signalé.
    Deux niveaux :
        • ``depassement`` — réel > budget (consommation > 100 %)
        • ``alerte``      — seuil_pct ≤ consommation ≤ 100 %

    Une catégorie au budget NUL (non budgétée) n'est jamais en alerte tant que
    son réel reste nul ; dès qu'un réel est constaté sur un budget nul, c'est un
    dépassement (consommation non bornée → ``None`` en %). Garde
    anti-division-par-zéro partout. La société est imposée par l'appelant ; le
    réel des catégories matériel/sous-traitance dégrade proprement à 0 tant
    qu'aucune source cross-app n'expose un montant (frontière cross-app). Lecture
    seule — aucune écriture.
    """
    if seuil_pct is None:
        seuil_pct = Decimal('90')
    else:
        seuil_pct = Decimal(str(seuil_pct))
    seuil_pct = max(Decimal('0'), min(Decimal('100'), seuil_pct))

    data = couts_engages_vs_reels(company, projet)

    def _evaluer(budget_montant, reel_montant):
        """Renvoie ``(consommation_pct ou None, niveau)`` pour un couple."""
        if budget_montant is None or budget_montant == 0:
            # Budget nul : dépassement dès qu'un réel est constaté.
            if reel_montant > 0:
                return None, 'depassement'
            return Decimal('0'), 'ok'
        consommation = (
            reel_montant / budget_montant * Decimal('100')).quantize(
                Decimal('0.01'))
        if reel_montant > budget_montant:
            niveau = 'depassement'
        elif consommation >= seuil_pct:
            niveau = 'alerte'
        else:
            niveau = 'ok'
        return consommation, niveau

    alertes = []
    for ligne in data['par_categorie']:
        consommation, niveau = _evaluer(ligne['budget'], ligne['reel'])
        if niveau != 'ok':
            alertes.append({
                'portee': 'categorie',
                'categorie': ligne['categorie'],
                'budget': ligne['budget'],
                'reel': ligne['reel'],
                'depassement': ligne['reel'] - ligne['budget'],
                'consommation_pct': consommation,
                'niveau': niveau,
            })

    total = data['total']
    consommation_totale, niveau_total = _evaluer(
        total['budget'], total['reel'])

    return {
        'budget_id': data['budget_id'],
        'budget_version': data['budget_version'],
        'budget_statut': data['budget_statut'],
        'seuil_pct': seuil_pct,
        'total': {
            'budget': total['budget'],
            'reel': total['reel'],
            'depassement': total['reel'] - total['budget'],
            'consommation_pct': consommation_totale,
            'niveau': niveau_total,
        },
        'alertes': alertes,
        'nb_alertes': len(alertes),
        'en_depassement': (
            niveau_total == 'depassement'
            or any(a['niveau'] == 'depassement' for a in alertes)),
    }


# ── Suivi des temps (PROJ24) ─────────────────────────────────────────────────
def timesheets_for_projet(projet):
    """Feuilles de temps d'un projet (QuerySet scopé société, plus récentes
    d'abord)."""
    return Timesheet.objects.filter(
        projet=projet, company=projet.company).select_related(
            'ressource', 'tache', 'phase').order_by('-date', '-id')


def synthese_temps_projet(projet):
    """Synthèse des temps imputés à un projet (PROJ24) — lecture seule.

    Agrège les feuilles de temps (``Timesheet``) du projet : total des
    ``heures`` et du ``cout`` INTERNE figé, puis ventilation par RESSOURCE et
    par TÂCHE. Données 100 % INTERNES de pilotage — jamais exposées au client.
    Le coût agrégé sert de source ALTERNATIVE de main-d'œuvre réelle (à côté des
    affectations). Une seule passe en mémoire ; ne MODIFIE rien.

    XPRJ2 — ventile en plus les heures FACTURABLES vs NON-facturables (total +
    par ressource) et par ``type_activite``. ``cout``/``cout_horaire`` INTERNES
    restent absents de toute sortie — seules les heures sont ventilées ici
    (``taux_facturation`` client, distinct du coût interne, n'est PAS agrégé en
    montant par ce sélecteur : voir ``services`` pour la facturation en régie).
    """
    timesheets = list(timesheets_for_projet(projet))
    total_heures = Decimal('0')
    total_cout = Decimal('0')
    heures_facturables = Decimal('0')
    heures_non_facturables = Decimal('0')
    par_ressource = {}
    par_tache = {}
    par_activite = {}
    for ts in timesheets:
        heures = ts.heures or Decimal('0')
        cout = ts.cout or Decimal('0')
        total_heures += heures
        total_cout += cout
        if ts.facturable:
            heures_facturables += heures
        else:
            heures_non_facturables += heures
        r = par_ressource.setdefault(ts.ressource_id, {
            'ressource_id': ts.ressource_id,
            'ressource_nom': ts.ressource.nom if ts.ressource_id else '',
            'heures': Decimal('0'),
            'cout': Decimal('0'),
            'heures_facturables': Decimal('0'),
        })
        r['heures'] += heures
        r['cout'] += cout
        if ts.facturable:
            r['heures_facturables'] += heures
        if ts.tache_id is not None:
            t = par_tache.setdefault(ts.tache_id, {
                'tache_id': ts.tache_id,
                'tache_libelle': ts.tache.libelle if ts.tache_id else '',
                'heures': Decimal('0'),
                'cout': Decimal('0'),
            })
            t['heures'] += heures
            t['cout'] += cout
        a = par_activite.setdefault(ts.type_activite, {
            'type_activite': ts.type_activite,
            'type_activite_display': ts.get_type_activite_display(),
            'heures': Decimal('0'),
            'heures_facturables': Decimal('0'),
        })
        a['heures'] += heures
        if ts.facturable:
            a['heures_facturables'] += heures
    return {
        'total_heures': total_heures,
        'total_cout': total_cout,
        'heures_facturables': heures_facturables,
        'heures_non_facturables': heures_non_facturables,
        'nb_saisies': len(timesheets),
        'par_ressource': sorted(
            par_ressource.values(), key=lambda x: x['ressource_id']),
        'par_tache': sorted(
            par_tache.values(), key=lambda x: x['tache_id']),
        'par_activite': sorted(
            par_activite.values(), key=lambda x: x['type_activite']),
    }


# ── Grille hebdomadaire de saisie des temps (XPRJ6) ──────────────────────────
def grille_semaine_temps(ressource, debut_semaine):
    """Grille hebdomadaire de saisie des temps d'une ressource (XPRJ6).

    ``debut_semaine`` est le PREMIER jour (date) de la fenêtre de 7 jours
    inclusive analysée : ``[debut_semaine, debut_semaine + 6 jours]``. Regroupe
    les ``Timesheet`` de la ressource sur cette fenêtre par (projet, tâche) —
    une ligne de grille par couple rencontré — avec les heures par jour
    (index 0 = ``debut_semaine`` … 6 = dernier jour) et le total de la ligne ;
    calcule aussi le total par jour et le total de la semaine. Lecture seule,
    scopée société (celle de la ressource).

    Ajoute des SUGGESTIONS de pré-remplissage dérivées des
    ``AffectationRessource`` DIRECTES (vecteur ``ressource`` — jamais via
    équipe ni actif matériel, une suggestion de temps est individuelle) de la
    ressource dont la fenêtre chevauche la semaine : une suggestion par
    (projet, tâche, jour OUVRÉ de l'affectation dans la semaine) SANS saisie
    déjà existante ce jour-là pour ce couple — jamais une ligne déjà couverte
    par une timesheet réelle. Les suggestions ne sont QUE proposées : rien
    n'est jamais écrit ici (le clic d'acceptation crée la ``Timesheet`` via
    l'endpoint de création standard).

    Renvoie ``{debut_semaine, fin_semaine, jours: [7 dates ISO],
    lignes: [{projet, projet_code, tache, tache_libelle, heures: [7],
    total_ligne}], total_par_jour: [7], total_semaine,
    suggestions: [{projet, projet_code, tache, tache_libelle, jour_index,
    date}]}``.
    """
    fin_semaine = debut_semaine + timedelta(days=6)
    jours = [debut_semaine + timedelta(days=i) for i in range(7)]

    timesheets = list(Timesheet.objects.filter(
        ressource=ressource, company=ressource.company,
        date__gte=debut_semaine, date__lte=fin_semaine,
    ).select_related('projet', 'tache').order_by('date', 'id'))

    lignes_par_cle = {}
    total_par_jour = [Decimal('0') for _ in range(7)]
    saisi_par_cle_jour = set()  # {(projet_id, tache_id, jour_index)}
    for ts in timesheets:
        idx = (ts.date - debut_semaine).days
        if idx < 0 or idx > 6:
            continue  # pragma: no cover - garanti par le filtre de date
        cle = (ts.projet_id, ts.tache_id)
        ligne = lignes_par_cle.setdefault(cle, {
            'projet': ts.projet_id,
            'projet_code': ts.projet.code if ts.projet_id else '',
            'tache': ts.tache_id,
            'tache_libelle': ts.tache.libelle if ts.tache_id else '',
            'heures': [Decimal('0') for _ in range(7)],
            'total_ligne': Decimal('0'),
        })
        heures = ts.heures or Decimal('0')
        ligne['heures'][idx] += heures
        ligne['total_ligne'] += heures
        total_par_jour[idx] += heures
        saisi_par_cle_jour.add((ts.projet_id, ts.tache_id, idx))

    total_semaine = sum(total_par_jour, Decimal('0'))

    # ── Suggestions depuis les affectations directes (jamais auto-enregistrées).
    affectations = AffectationRessource.objects.filter(
        ressource=ressource, company=ressource.company,
        date_debut__lte=fin_semaine, date_fin__gte=debut_semaine,
    ).select_related('tache', 'tache__projet')

    suggestions = []
    vues = set()  # anti-doublon si plusieurs affectations couvrent le même jour
    for aff in affectations:
        tache = aff.tache
        if tache is None:
            continue
        projet_id = tache.projet_id
        for idx, jour in enumerate(jours):
            if jour < aff.date_debut or jour > aff.date_fin:
                continue
            cle = (projet_id, tache.id, idx)
            if cle in saisi_par_cle_jour or cle in vues:
                continue
            vues.add(cle)
            suggestions.append({
                'projet': projet_id,
                'projet_code': tache.projet.code if projet_id else '',
                'tache': tache.id,
                'tache_libelle': tache.libelle,
                'jour_index': idx,
                'date': jour.isoformat(),
            })
    suggestions.sort(key=lambda s: (s['jour_index'], s['tache'] or 0))

    return {
        'debut_semaine': debut_semaine.isoformat(),
        'fin_semaine': fin_semaine.isoformat(),
        'jours': [j.isoformat() for j in jours],
        'lignes': sorted(
            lignes_par_cle.values(),
            key=lambda ligne: (ligne['projet_code'], ligne['tache_libelle'])),
        'total_par_jour': total_par_jour,
        'total_semaine': total_semaine,
        'suggestions': suggestions,
    }


# ── Détection des temps manquants (XPRJ7) ────────────────────────────────────
def temps_manquants(company, debut, fin):
    """Jours SANS saisie de temps par ressource ACTIVE liée à un user (XPRJ7).

    Pour chaque ``RessourceProfil`` ACTIVE de la société PORTANT un ``user``
    lié (une ressource sans compte ERP n'a personne à relancer) : compare les
    jours OUVRÉS (semaine L-V par défaut, ``_JOURS_OUVRES_DEFAUT`` — même
    convention que ``plan_de_charge``) de la fenêtre [debut, fin] (INCLUSIVE)
    MOINS les jours couverts par une ``Indisponibilite`` chevauchante, à
    l'ensemble des ``date`` distinctes où une ``Timesheet`` existe pour cette
    ressource. Les jours ouvrés attendus SANS saisie sont listés en clair.

    Lecture seule, multi-société : toutes les données lues sont filtrées sur
    ``company``. ``fin < debut`` → aucun jour attendu pour personne. Renvoie
    un dict ``{debut, fin, lignes: [{ressource_id, ressource_nom, user_id,
    jours_attendus, jours_saisis, jours_manquants: [date, ...]}]}`` trié par
    nom de ressource ; seules les ressources avec AU MOINS un jour manquant
    figurent dans ``lignes``.
    """
    if fin < debut:
        return {'debut': debut, 'fin': fin, 'lignes': []}

    jours_ouvres = _JOURS_OUVRES_DEFAUT

    # Tous les jours OUVRÉS de la fenêtre (indépendants de la ressource).
    tous_jours_ouvres = []
    cur = debut
    while cur <= fin:
        if cur.weekday() in jours_ouvres:
            tous_jours_ouvres.append(cur)
        cur += timedelta(days=1)

    ressources = RessourceProfil.objects.filter(
        company=company, actif=True, user__isnull=False)

    lignes = []
    for ressource in ressources.order_by('nom', 'id'):
        indispos = list(Indisponibilite.objects.filter(
            company=company, ressource=ressource,
            date_debut__lte=fin, date_fin__gte=debut))

        def _indisponible(jour, indispos=indispos):
            return any(i.date_debut <= jour <= i.date_fin for i in indispos)

        jours_attendus = [
            j for j in tous_jours_ouvres if not _indisponible(j)]
        if not jours_attendus:
            continue

        jours_saisis = set(Timesheet.objects.filter(
            company=company, ressource=ressource,
            date__gte=debut, date__lte=fin,
        ).values_list('date', flat=True))

        jours_manquants = [j for j in jours_attendus if j not in jours_saisis]
        if not jours_manquants:
            continue

        lignes.append({
            'ressource_id': ressource.id,
            'ressource_nom': ressource.nom,
            'user_id': ressource.user_id,
            'jours_attendus': len(jours_attendus),
            'jours_saisis': len(
                [j for j in jours_attendus if j in jours_saisis]),
            'jours_manquants': jours_manquants,
        })

    return {'debut': debut, 'fin': fin, 'lignes': lignes}


# ── Heures attendues & heures supplémentaires (ZPRJ5) ────────────────────────
def heures_attendues_vs_saisies(company, ressource, debut, fin):
    """Écart heures ATTENDUES vs SAISIES pour UNE ressource sur [debut, fin]
    (ZPRJ5) — sous-charge / heures supplémentaires, par jour et cumulé.

    Distinct de ``temps_manquants`` (XPRJ7, jours SANS AUCUNE saisie) : ici on
    QUANTIFIE l'écart d'HEURES, y compris pour un jour partiellement saisi.
    Pour chaque jour OUVRÉ (semaine L-V par défaut, ``_JOURS_OUVRES_DEFAUT``)
    de la fenêtre INCLUSIVE [debut, fin] NON couvert par une
    ``Indisponibilite`` chevauchante de la ressource : l'attendu du jour =
    ``heures_par_jour`` du réglage temps de la société (ZPRJ1,
    ``_heures_par_jour_reglage`` — get_or_create-free, LECTURE SEULE) ; le
    saisi du jour = somme des ``Timesheet.heures`` de la ressource CE jour.
    L'écart du jour = saisi − attendu (positif = heures supplémentaires,
    négatif = sous-charge, zéro = pile l'attendu). Un jour d'indisponibilité
    n'a AUCUN attendu (exclu de ``jours_attendus`` et absent de ``par_jour``).

    Lecture seule, multi-société : toutes les données lues sont filtrées sur
    ``company`` (la ressource doit appartenir à la MÊME société — l'appelant
    est responsable de ce scoping, comme pour les autres sélecteurs par
    ressource). ``fin < debut`` → aucun jour attendu (garde explicite). Une
    ressource sans ``user`` lié reste calculable (l'appelant décide s'il
    notifie ou non — pas de filtre ici, contrairement à ``temps_manquants``).
    Renvoie un dict ``{debut, fin, heures_attendues_jour, jours_attendus,
    total_attendu, total_saisi, ecart_cumule, par_jour: [{date, attendu,
    saisi, ecart}, ...]}``.
    """
    heures_attendues_jour = float(_heures_par_jour_reglage(company))
    base = {
        'debut': debut.isoformat(), 'fin': fin.isoformat(),
        'heures_attendues_jour': heures_attendues_jour,
        'jours_attendus': 0,
        'total_attendu': 0.0, 'total_saisi': 0.0, 'ecart_cumule': 0.0,
        'par_jour': [],
    }
    if fin < debut:
        return base

    jours_ouvres = _JOURS_OUVRES_DEFAUT
    indispos = list(Indisponibilite.objects.filter(
        company=company, ressource=ressource,
        date_debut__lte=fin, date_fin__gte=debut))

    def _indisponible(jour):
        return any(i.date_debut <= jour <= i.date_fin for i in indispos)

    saisies_par_jour = {}
    for ts in Timesheet.objects.filter(
            company=company, ressource=ressource,
            date__gte=debut, date__lte=fin):
        saisies_par_jour[ts.date] = (
            saisies_par_jour.get(ts.date, Decimal('0')) + (ts.heures or Decimal('0')))

    par_jour = []
    total_attendu = 0.0
    total_saisi = 0.0
    cur = debut
    while cur <= fin:
        if cur.weekday() in jours_ouvres and not _indisponible(cur):
            saisi = float(saisies_par_jour.get(cur, Decimal('0')))
            ecart = saisi - heures_attendues_jour
            par_jour.append({
                'date': cur.isoformat(),
                'attendu': heures_attendues_jour,
                'saisi': round(saisi, 2),
                'ecart': round(ecart, 2),
            })
            total_attendu += heures_attendues_jour
            total_saisi += saisi
        cur += timedelta(days=1)

    base['jours_attendus'] = len(par_jour)
    base['total_attendu'] = round(total_attendu, 2)
    base['total_saisi'] = round(total_saisi, 2)
    base['ecart_cumule'] = round(total_saisi - total_attendu, 2)
    base['par_jour'] = par_jour
    return base


# ── Classement de saisie des temps — leaderboard interne (ZPRJ6) ────────────
def classement_temps(company, debut, fin):
    """Classement de saisie des temps par ``RessourceProfil`` (ZPRJ6).

    Odoo Timesheets a un leaderboard gamifié (heures encodées, complétude)
    pour inciter à la saisie. Pour CHAQUE ``RessourceProfil`` ACTIVE liée à un
    ``user`` (une ressource sans compte ERP n'a rien à « classer ») sur
    [debut, fin] : ``total_heures`` saisies (réutilise ``heures_attendues_vs_
    saisies`` — ZPRJ5, ``total_saisi``), ``taux_completude_pct`` (jours saisis
    / jours ouvrés attendus × 100, réutilise le même sélecteur — arrondi 1
    décimale, ``None`` si aucun jour attendu, GARDE division par zéro),
    ``jours_de_retard`` (jours ouvrés attendus SANS AUCUNE saisie sur la
    fenêtre — même comptage que ``temps_manquants``/XPRJ7, calculé ici
    directement pour rester cohérent avec le même sélecteur ZPRJ5 déjà
    exécuté, sans le ré-invoquer).

    AUCUN montant/coût interne (``cout``/``cout_horaire``) n'est exposé ici —
    seules les heures et la complétude, jamais une donnée de pilotage
    financier. Lecture seule, multi-société. Trié par ``taux_completude_pct``
    DÉCROISSANT puis ``total_heures`` DÉCROISSANT (les plus assidus d'abord).
    Renvoie ``{'debut', 'fin', 'lignes': [{ressource_id, ressource_nom,
    total_heures, taux_completude_pct, jours_de_retard}, ...]}``.
    """
    ressources = RessourceProfil.objects.filter(
        company=company, actif=True, user__isnull=False)

    lignes = []
    for ressource in ressources.order_by('nom', 'id'):
        data = heures_attendues_vs_saisies(company, ressource, debut, fin)
        jours_attendus = data['jours_attendus']
        jours_saisis = sum(
            1 for jour in data['par_jour'] if jour['saisi'] > 0)
        if jours_attendus > 0:
            taux_completude_pct = round(
                jours_saisis / jours_attendus * 100, 1)
        else:
            taux_completude_pct = None
        jours_de_retard = jours_attendus - jours_saisis

        lignes.append({
            'ressource_id': ressource.id,
            'ressource_nom': ressource.nom,
            'total_heures': data['total_saisi'],
            'taux_completude_pct': taux_completude_pct,
            'jours_de_retard': jours_de_retard,
        })

    lignes.sort(key=lambda ln: (
        -(ln['taux_completude_pct'] or 0), -ln['total_heures']))

    return {'debut': debut.isoformat(), 'fin': fin.isoformat(),
            'lignes': lignes}


# ── Rapprochement pointages RH ↔ temps projet (XPRJ8) ────────────────────────
def rapprochement_pointages(company, debut, fin, seuil_heures=Decimal('0.5')):
    """Croise pointages RH (FG166) et temps projet, par employé/jour (XPRJ8).

    Pour chaque ``RessourceProfil`` ACTIVE liée à un ``user`` : agrège la durée
    POINTÉE (via ``apps.rh.selectors.pointages_par_user_jour`` — frontière
    cross-app, import fonction-local, JAMAIS ``rh.models``) et les heures de
    ``Timesheet`` de la ressource, par jour, sur [debut, fin] (inclusif).
    Signale un ÉCART pour chaque jour où :

    * pointé SANS imputation — un pointage existe, aucune timesheet ce jour ;
    * imputé SANS pointage — une timesheet existe, aucun pointage ce jour ;
    * delta d'heures — les deux existent mais divergent de plus de
      ``seuil_heures`` (défaut 0.5 h = 30 min).

    Dégrade PROPREMENT si ``rh`` n'expose aucun pointage (dict vide) — aucune
    exception ne remonte. Lecture seule, multi-société. Renvoie un dict
    ``{debut, fin, ecarts: [{ressource_id, ressource_nom, date, type_ecart,
    heures_pointees, heures_imputees}]}`` trié par ressource puis date.
    """
    if fin < debut:
        return {'debut': debut, 'fin': fin, 'ecarts': []}

    try:
        from apps.rh import selectors as rh_selectors
        pointages = rh_selectors.pointages_par_user_jour(company, debut, fin)
    except Exception:  # pragma: no cover - défensif, dégrade proprement
        pointages = {}

    ressources = RessourceProfil.objects.filter(
        company=company, actif=True, user__isnull=False)

    timesheets = Timesheet.objects.filter(
        company=company, ressource__in=ressources,
        date__gte=debut, date__lte=fin,
    ).values('ressource_id', 'date').annotate(total_heures=Sum('heures'))
    heures_imputees_par_res_jour = {
        (row['ressource_id'], row['date']): row['total_heures'] or Decimal('0')
        for row in timesheets
    }

    ecarts = []
    for ressource in ressources.order_by('nom', 'id'):
        cur = debut
        while cur <= fin:
            minutes_pointees = pointages.get((ressource.user_id, cur))
            heures_imputees = heures_imputees_par_res_jour.get(
                (ressource.id, cur))
            a_pointage = minutes_pointees is not None
            a_imputation = heures_imputees is not None

            if not a_pointage and not a_imputation:
                cur += timedelta(days=1)
                continue

            heures_pointees = (
                Decimal(minutes_pointees) / Decimal('60')
            ).quantize(Decimal('0.01')) if a_pointage else Decimal('0')
            heures_imputees_val = heures_imputees or Decimal('0')

            if a_pointage and not a_imputation:
                type_ecart = 'pointe_sans_imputation'
            elif a_imputation and not a_pointage:
                type_ecart = 'impute_sans_pointage'
            elif abs(heures_pointees - heures_imputees_val) > seuil_heures:
                type_ecart = 'delta_heures'
            else:
                cur += timedelta(days=1)
                continue

            ecarts.append({
                'ressource_id': ressource.id,
                'ressource_nom': ressource.nom,
                'date': cur,
                'type_ecart': type_ecart,
                'heures_pointees': heures_pointees,
                'heures_imputees': heures_imputees_val,
            })
            cur += timedelta(days=1)

    return {'debut': debut, 'fin': fin, 'ecarts': ecarts}


# ── Consommation matière vs BoM (PROJ25) ─────────────────────────────────────
def _consommation_matiere_cross_app(projet):
    """Consommation matière RÉELLE d'un projet via les apps cibles (ou dégrade).

    Tente d'agréger la matière consommée sur les CHANTIERS rattachés au projet
    (``ProjetChantier``) en appelant un sélecteur de l'app ``installations`` —
    SANS jamais importer ses ``models``/``views`` (frontière cross-app,
    CLAUDE.md ; import fonction-local). Aucune app cible n'expose aujourd'hui de
    sélecteur de consommation matière par chantier exploitable ici → on DÉGRADE
    proprement : montant consommé à 0 et une note. Aucune exception ne remonte.

    Renvoie ``(montant_consomme: Decimal, source: str, note: str)``.
    """
    from .models import ProjetChantier
    nb_chantiers = ProjetChantier.objects.filter(
        projet=projet, company=projet.company).count()
    nb_liens_achat = ProjetLien.objects.filter(
        projet=projet, company=projet.company,
        type_cible=ProjetLien.TypeCible.ACHAT).count()
    # Pas de sélecteur cross-app de consommation matière disponible → dégrade.
    if nb_chantiers or nb_liens_achat:
        note = (
            f"{nb_chantiers} chantier(s) et {nb_liens_achat} achat(s) "
            "rattaché(s) : consommation matière non disponible (aucun "
            "sélecteur cross-app) — consommé à 0.")
    else:
        note = ("Aucun chantier ni achat rattaché — consommé à 0.")
    return Decimal('0'), 'degrade', note


def consommation_matiere_vs_bom(projet):
    """Consommation matière RÉELLE vs BoM PRÉVISIONNELLE d'un projet (PROJ25).

    La BoM (Bill of Materials) prévisionnelle est ASSIMILÉE aux lignes de budget
    de catégorie ``materiel`` du budget de référence (``budget_effectif``) : la
    somme des ``montant_prevu`` matériel donne le PLANIFIÉ. La consommation
    RÉELLE est agrégée via ``installations`` (chantiers rattachés) / ``stock``
    (achats rattachés) — toujours en passant par un sélecteur de l'app cible,
    jamais en important ses modèles (frontière cross-app, CLAUDE.md). Aucune
    app cible n'expose aujourd'hui ce montant → DÉGRADE : consommé à 0 + note.

    Renvoie ``{bom_prevu, consomme, ecart (prévu − consommé), ecart_pct (None si
    prévu == 0 — garde division-par-zéro), source, note, budget_id,
    budget_version}``. Tout est scopé société via le projet. Lecture seule.
    """
    budget = budget_effectif(projet)
    if budget is not None:
        agg = budget_total(budget)
        bom_prevu = agg['par_categorie'].get(
            LigneBudgetProjet.Categorie.MATERIEL, Decimal('0'))
        budget_id = budget.id
        budget_version = budget.version
    else:
        bom_prevu = Decimal('0')
        budget_id = None
        budget_version = None

    consomme, source, note = _consommation_matiere_cross_app(projet)
    ecart = bom_prevu - consomme
    ecart_pct = _ecart_pct(bom_prevu, consomme)
    return {
        'bom_prevu': bom_prevu,
        'consomme': consomme,
        'ecart': ecart,
        'ecart_pct': ecart_pct,
        'source': source,
        'note': note,
        'budget_id': budget_id,
        'budget_version': budget_version,
    }


# ── P&L de projet consolidé (PROJ26 — interne/admin) ─────────────────────────
def _revenu_projet_cross_app(projet):
    """Revenu (CA) RÉEL d'un projet via les apps cibles (ou dégrade).

    Agrège le chiffre d'affaires des devis/factures rattachés au projet
    (``ProjetLien`` type devis/facture) en passant par un sélecteur de l'app
    ``ventes`` — SANS jamais importer ses ``models``/``views`` (frontière
    cross-app, CLAUDE.md ; import fonction-local). Aucune app cible n'expose
    aujourd'hui de sélecteur de MONTANT par projet exploitable → DÉGRADE :
    revenu à 0 + note (nb de liens devis/facture). Aucune exception ne remonte.

    Renvoie ``(revenu: Decimal, note: str)``.
    """
    nb_liens_revenu = ProjetLien.objects.filter(
        projet=projet, company=projet.company,
        type_cible__in=(
            ProjetLien.TypeCible.DEVIS,
            ProjetLien.TypeCible.FACTURE)).count()
    if nb_liens_revenu:
        note = (
            f"{nb_liens_revenu} devis/facture(s) rattaché(s) : montant non "
            "disponible (aucun sélecteur cross-app) — revenu à 0.")
    else:
        note = "Aucun devis/facture rattaché — revenu à 0."
    return Decimal('0'), note


def pnl_projet(company, projet):
    """Compte de résultat (P&L) CONSOLIDÉ d'un projet (PROJ26 — interne/admin).

    Donnée 100 % INTERNE de pilotage — JAMAIS exposée au client final (rejoint
    ``budget_total``, ``cout_horaire``). Consolide :

      • ``revenu``   — CA des devis/factures rattachés (``ProjetLien``) via un
        sélecteur ``ventes`` ; dégrade à 0 + note (frontière cross-app).
      • ``cout_budget`` — total prévisionnel du budget de référence (PROJ21).
      • ``cout_reel``   — réel consolidé : main-d'œuvre des affectations
        (PROJ22) + coût figé des timesheets (PROJ24) + matériel/sous-traitance
        des liens de dépense (dégradés à 0 tant qu'aucun sélecteur cross-app
        n'expose le montant).
      • ``marge_prev``  = revenu − cout_budget ; ``marge_reelle`` = revenu −
        cout_reel ; ``marge_pct_reelle`` = marge_reelle / revenu × 100 (None si
        revenu == 0 — garde division-par-zéro).

    Tout est scopé société via le projet. Lecture seule (aucune écriture).
    """
    # Revenu (dégrade cross-app).
    revenu, note_revenu = _revenu_projet_cross_app(projet)

    # Coûts : budget prévisionnel + réel consolidé.
    couts = couts_engages_vs_reels(company, projet)
    cout_budget = couts['total']['budget']
    cout_reel_affectations = couts['total']['reel']

    # Réel issu des timesheets (PROJ24) — source interne complémentaire.
    synthese_ts = synthese_temps_projet(projet)
    cout_timesheets = synthese_ts['total_cout']

    # Le réel consolidé additionne affectations (PROJ22) et timesheets (PROJ24) :
    # ce sont deux sources INTERNES distinctes de main-d'œuvre réelle.
    cout_reel = cout_reel_affectations + cout_timesheets

    marge_prev = revenu - cout_budget
    marge_reelle = revenu - cout_reel
    if revenu and revenu != 0:
        marge_pct_reelle = (
            marge_reelle / revenu * Decimal('100')).quantize(Decimal('0.01'))
    else:
        marge_pct_reelle = None

    return {
        'revenu': revenu,
        'note_revenu': note_revenu,
        'cout_budget': cout_budget,
        'cout_reel': cout_reel,
        'cout_reel_affectations': cout_reel_affectations,
        'cout_reel_timesheets': cout_timesheets,
        'marge_prev': marge_prev,
        'marge_reelle': marge_reelle,
        'marge_pct_reelle': marge_pct_reelle,
        'budget_id': couts['budget_id'],
        'budget_version': couts['budget_version'],
        'couts_par_categorie': couts['par_categorie'],
    }


# ── Jalons de facturation liés à l'avancement (PROJ27) ───────────────────────
def jalons_facturables(projet):
    """Jalons de FACTURATION d'un projet déclenchables par l'avancement (PROJ27).

    Un jalon est « facturable » quand il porte un ``facturation_pct`` > 0 ET
    qu'il est ATTEINT (``statut == atteint``). Le ``montant`` théorique est
    ``facturation_pct`` % du ``budget_total`` du projet (donnée INTERNE de
    pilotage) — le montant client réel reste piloté par ``ventes`` (le service
    ``declencher_facturation_jalon`` route l'écriture vers ``ventes.services``).

    Renvoie ``{base_montant, total_pct_facture, jalons: [...]}`` où chaque jalon
    porte ``{id, libelle, facturation_pct, statut, atteint, facturable,
    montant}``. ``atteint`` recoupe le statut ; ``facturable`` exige atteint +
    pct > 0. Tout est scopé société via le projet. Lecture seule.
    """
    base = projet.budget_total or Decimal('0')
    jalons = jalons_for_projet(projet)
    lignes = []
    total_pct_facture = Decimal('0')
    for jalon in jalons:
        pct = jalon.facturation_pct or Decimal('0')
        atteint = jalon.statut == Jalon.Statut.ATTEINT
        facturable = atteint and pct > 0
        montant = (base * pct / Decimal('100')).quantize(Decimal('0.01'))
        if facturable:
            total_pct_facture += pct
        lignes.append({
            'id': jalon.id,
            'libelle': jalon.libelle,
            'facturation_pct': pct,
            'statut': jalon.statut,
            'atteint': atteint,
            'facturable': facturable,
            'montant': montant,
        })
    return {
        'base_montant': base,
        'total_pct_facture': total_pct_facture,
        'jalons': lignes,
    }


# ── Suivi avancement vs facturé (PROJ28) ─────────────────────────────────────
def avancement_vs_facture(projet):
    """Compare l'AVANCEMENT physique d'un projet à ce qui est FACTURÉ (PROJ28).

    L'avancement PHYSIQUE est le roll-up pondéré par charge des tâches (PROJ9).
    Le % FACTURÉ est la somme des ``facturation_pct`` des jalons de facturation
    ATTEINTS (PROJ7/PROJ27) — borné à 100. L'``ecart_pct`` = avancement − facturé
    indique :
        • > 0 : on a AVANCÉ plus qu'on n'a facturé (sous-facturation, trésorerie
          à rattraper) ;
        • < 0 : on a FACTURÉ d'avance par rapport à l'avancement.

    Renvoie ``{avancement_pct, facture_pct, ecart_pct, base_montant,
    montant_facture, montant_avancement}`` où les montants sont des projections
    INTERNES (% × ``budget_total``). Tout est scopé société via le projet.
    Lecture seule (aucune écriture).
    """
    avancement = rollup_avancement(projet)
    avancement_pct = Decimal(str(avancement['avancement_pct']))

    facturables = jalons_facturables(projet)
    facture_pct = min(
        facturables['total_pct_facture'], Decimal('100'))

    base = projet.budget_total or Decimal('0')
    montant_facture = (
        base * facture_pct / Decimal('100')).quantize(Decimal('0.01'))
    montant_avancement = (
        base * avancement_pct / Decimal('100')).quantize(Decimal('0.01'))

    return {
        'avancement_pct': avancement_pct,
        'facture_pct': facture_pct,
        'ecart_pct': avancement_pct - facture_pct,
        'base_montant': base,
        'montant_facture': montant_facture,
        'montant_avancement': montant_avancement,
    }


# ── EVM léger — valeur acquise (PROJ29, optionnel) ───────────────────────────
def evm_projet(company, projet, date_reference=None):
    """Valeur acquise (EVM) LÉGER d'un projet (PROJ29) — interne/admin.

    Indicateurs classiques (donnée 100 % INTERNE de pilotage) :
        • BAC (Budget At Completion) = ``budget_total`` du projet.
        • EV (Earned Value)  = avancement physique (PROJ9) × BAC.
        • AC (Actual Cost)   = coût RÉEL consolidé (affectations PROJ22 +
          timesheets PROJ24).
        • PV (Planned Value) = fraction de calendrier ÉCOULÉE × BAC, calculée
          entre ``date_debut`` et ``date_fin_prevue`` à la ``date_reference``
          (défaut : aujourd'hui). Sans dates de projet, PV = None (EVM léger).
        • CV = EV − AC ; SV = EV − PV ; CPI = EV / AC ; SPI = EV / PV.

    Toutes les divisions sont gardées (dénominateur nul → indicateur None).
    Tout est scopé société via le projet. Lecture seule (aucune écriture).
    """
    if date_reference is None:
        date_reference = _date.today()

    bac = projet.budget_total or Decimal('0')

    # EV : avancement physique × BAC.
    avancement = rollup_avancement(projet)
    avancement_pct = Decimal(str(avancement['avancement_pct']))
    ev = (bac * avancement_pct / Decimal('100')).quantize(Decimal('0.01'))

    # AC : réel consolidé (affectations + timesheets).
    couts = couts_engages_vs_reels(company, projet)
    synthese_ts = synthese_temps_projet(projet)
    ac = (couts['total']['reel'] + synthese_ts['total_cout'])

    # PV : fraction de calendrier écoulée × BAC.
    pv = None
    fraction_ecoulee = None
    debut = projet.date_debut
    fin = projet.date_fin_prevue
    if debut is not None and fin is not None and fin > debut:
        if date_reference <= debut:
            fraction = Decimal('0')
        elif date_reference >= fin:
            fraction = Decimal('1')
        else:
            ecoule = (date_reference - debut).days
            total = (fin - debut).days
            fraction = (Decimal(ecoule) / Decimal(total))
        fraction_ecoulee = (fraction * Decimal('100')).quantize(Decimal('0.01'))
        pv = (bac * fraction).quantize(Decimal('0.01'))

    def _div(num, den):
        if den is None or den == 0:
            return None
        return (num / den).quantize(Decimal('0.0001'))

    cv = ev - ac
    sv = (ev - pv) if pv is not None else None
    cpi = _div(ev, ac)
    spi = _div(ev, pv) if pv is not None else None

    return {
        'bac': bac,
        'ev': ev,
        'ac': ac,
        'pv': pv,
        'avancement_pct': avancement_pct,
        'fraction_ecoulee_pct': fraction_ecoulee,
        'cv': cv,
        'sv': sv,
        'cpi': cpi,
        'spi': spi,
        'date_reference': date_reference,
    }


# ── Prévision fin de projet — ETC/EAC (XPRJ16) ───────────────────────────────
def prevision_fin_projet(projet, date_reference=None):
    """Prévision fin de projet PAR CATÉGORIE de budget (XPRJ16) — interne/admin.

    Pour CHAQUE catégorie canonique de budget (PROJ21 : matériel /
    main-d'œuvre / sous-traitance / divers) :
        • ETC (Estimate To Complete) = (budget − réel) ajusté du CPI courant
          de l'EVM (PROJ29). CPI = EV/AC globalement projet (pas par
          catégorie — l'EVM n'est pas ventilé par catégorie).
              CPI absent/nul → ETC = budget restant (budget − réel), non ajusté
              (garde division-par-zéro : pas d'ajustement de performance).
        • EAC (Estimate At Completion) = réel + ETC.
        • écart EAC vs budget + % (garde division par zéro : budget nul →
          ``ecart_pct`` = None).

    Donnée 100 % INTERNE de pilotage — jamais un montant dans le portail
    client (``portail_avancement_client``, PROJ37, reste inchangé). Tout est
    scopé société via le projet. Lecture seule.
    """
    company = projet.company
    couts = couts_engages_vs_reels(company, projet)
    evm = evm_projet(company, projet, date_reference=date_reference)
    cpi = evm['cpi']

    def _ecart_pct_local(eac, budget):
        if not budget:
            return None
        return ((eac - budget) / budget * Decimal('100')).quantize(
            Decimal('0.01'))

    par_categorie = []
    total_etc = Decimal('0')
    total_eac = Decimal('0')
    for ligne in couts['par_categorie']:
        budget_montant = ligne['budget']
        reel_montant = ligne['reel']
        budget_restant = budget_montant - reel_montant
        if cpi is not None and cpi != 0:
            etc = (budget_restant / cpi).quantize(Decimal('0.01'))
        else:
            etc = budget_restant
        eac = reel_montant + etc
        total_etc += etc
        total_eac += eac
        par_categorie.append({
            'categorie': ligne['categorie'],
            'budget': budget_montant,
            'reel': reel_montant,
            'etc': etc,
            'eac': eac,
            'ecart_eac_budget': eac - budget_montant,
            'ecart_eac_budget_pct': _ecart_pct_local(eac, budget_montant),
        })

    return {
        'cpi': cpi,
        'budget_total': couts['total']['budget'],
        'reel_total': couts['total']['reel'],
        'etc_total': total_etc,
        'eac_total': total_eac,
        'ecart_eac_budget_total': total_eac - couts['total']['budget'],
        'ecart_eac_budget_total_pct': _ecart_pct_local(
            total_eac, couts['total']['budget']),
        'par_categorie': par_categorie,
    }


# ── Rapport des temps multi-dimensions (XPRJ18) ──────────────────────────────
_GROUP_BY_CHAMPS = {
    'ressource': ('ressource_id', 'ressource.nom'),
    'projet': ('projet_id', 'projet.code'),
    'tache': ('tache_id', 'tache.libelle'),
    'phase': ('phase_id', 'phase.libelle'),
    'type_activite': ('type_activite', None),
    'semaine': (None, None),  # calculé (année-ISO, semaine-ISO)
    'mois': (None, None),  # calculé (année-mois)
}


def _cle_groupe(ts, group_by):
    if group_by == 'semaine':
        iso = ts.date.isocalendar()
        return f'{iso[0]}-S{iso[1]:02d}'
    if group_by == 'mois':
        return f'{ts.date.year}-{ts.date.month:02d}'
    if group_by == 'ressource':
        return ts.ressource_id
    if group_by == 'projet':
        return ts.projet_id
    if group_by == 'tache':
        return ts.tache_id
    if group_by == 'phase':
        return ts.phase_id
    if group_by == 'type_activite':
        return ts.type_activite
    return None


def _libelle_groupe(ts, group_by):
    if group_by == 'semaine' or group_by == 'mois':
        return _cle_groupe(ts, group_by)
    if group_by == 'ressource':
        return ts.ressource.nom
    if group_by == 'projet':
        return ts.projet.code
    if group_by == 'tache':
        return ts.tache.libelle if ts.tache_id else '(sans tâche)'
    if group_by == 'phase':
        return ts.phase.libelle if ts.phase_id else '(sans phase)'
    if group_by == 'type_activite':
        return ts.get_type_activite_display()
    return ''


def rapport_temps(company, debut, fin, group_by='ressource'):
    """Rapport des temps MULTI-DIMENSIONS agrégé (XPRJ18) — interne/admin.

    Agrège les heures (et heures FACTURABLES, XPRJ2) sur la fenêtre
    ``[debut, fin]`` par dimension ``group_by`` parmi ressource / projet /
    tâche / phase / type_activite / semaine / mois (défaut ``ressource``,
    retombe dessus si ``group_by`` invalide). Pour CHAQUE tâche impliquée,
    ajoute le comparatif heures loguées vs ``charge_estimee`` (en heures,
    8h/jour) — un dépassement (heures > charge × 8) est FLAGGÉ
    ``depassement=True``. Donnée 100 % INTERNE de pilotage (jamais ``cout``
    dans l'export xlsx, voir vue). Tout est scopé société. Lecture seule.
    """
    if group_by not in _GROUP_BY_CHAMPS:
        group_by = 'ressource'

    timesheets = list(
        Timesheet.objects.filter(
            company=company, date__gte=debut, date__lte=fin)
        .select_related('ressource', 'projet', 'tache', 'phase'))

    groupes = {}
    ordre_cles = []
    for ts in timesheets:
        cle = _cle_groupe(ts, group_by)
        if cle not in groupes:
            groupes[cle] = {
                'cle': cle,
                'libelle': _libelle_groupe(ts, group_by),
                'heures': Decimal('0'),
                'heures_facturables': Decimal('0'),
                'cout': Decimal('0'),
            }
            ordre_cles.append(cle)
        groupes[cle]['heures'] += ts.heures
        if ts.facturable:
            groupes[cle]['heures_facturables'] += ts.heures
        groupes[cle]['cout'] += ts.cout

    lignes = [groupes[cle] for cle in ordre_cles]

    # Comparatif par tâche : heures loguées (sur la fenêtre) vs charge
    # estimée convertie en heures (8h/jour). Dépassement flaggé.
    taches_impliquees_ids = {
        ts.tache_id for ts in timesheets if ts.tache_id is not None}
    par_tache = []
    if taches_impliquees_ids:
        for tache in Tache.objects.filter(
                id__in=taches_impliquees_ids, company=company):
            heures_loguees = sum(
                (ts.heures for ts in timesheets if ts.tache_id == tache.id),
                Decimal('0'))
            charge_heures = (
                (tache.charge_estimee * Decimal('8'))
                if tache.charge_estimee is not None else None)
            depassement = (
                charge_heures is not None
                and heures_loguees > charge_heures)
            par_tache.append({
                'tache_id': tache.id,
                'libelle': tache.libelle,
                'heures_loguees': heures_loguees,
                'charge_estimee_heures': charge_heures,
                'depassement': depassement,
            })

    total_heures = sum((ts.heures for ts in timesheets), Decimal('0'))
    total_facturables = sum(
        (ts.heures for ts in timesheets if ts.facturable), Decimal('0'))

    return {
        'group_by': group_by,
        'lignes': lignes,
        'par_tache': par_tache,
        'total_heures': total_heures,
        'total_heures_facturables': total_facturables,
    }


# ── Burndown du projet (XPRJ17) ──────────────────────────────────────────────
def burndown(projet, debut, fin):
    """Série HEBDOMADAIRE de charge restante vs ligne idéale (XPRJ17).

    Pour chaque semaine (date de fin de semaine, pas de 7 jours depuis
    ``debut``) jusqu'à ``fin`` inclus : la charge restante = somme des
    ``charge_estimee`` des tâches NON TERMINÉES À CETTE DATE, reconstituée
    depuis ``date_fin_reelle`` (une tâche est "restante" tant qu'elle n'a pas
    encore de ``date_fin_reelle`` à la date considérée, ou que sa
    ``date_fin_reelle`` est postérieure). La ligne IDÉALE décroît linéairement
    de la charge totale à 0 entre ``debut`` et ``fin``. Les heures loguées
    CUMULÉES (timesheets) sont ajoutées par semaine pour comparaison.

    Un projet SANS AUCUNE charge estimée (toutes tâches à ``charge_estimee``
    None ou pas de tâche) renvoie une réponse vide propre (``points`` = []).
    Tout est scopé société via le projet. Lecture seule.
    """
    taches = list(Tache.objects.filter(
        projet=projet, company=projet.company,
        charge_estimee__isnull=False))
    charge_totale = sum((t.charge_estimee for t in taches), Decimal('0'))
    if not taches or charge_totale <= 0:
        return {'points': [], 'charge_totale': Decimal('0')}

    timesheets = list(Timesheet.objects.filter(
        projet=projet, company=projet.company,
        date__gte=debut, date__lte=fin).order_by('date'))

    duree_totale_jours = max((fin - debut).days, 1)
    points = []
    courant = debut
    heures_cumulees = Decimal('0')
    while courant <= fin:
        # Charge restante : somme des tâches pas encore terminées à cette
        # date (date_fin_reelle absente OU postérieure à ``courant``).
        restant = sum(
            (t.charge_estimee for t in taches
             if t.date_fin_reelle is None or t.date_fin_reelle > courant),
            Decimal('0'))

        ecoule_jours = (courant - debut).days
        fraction = min(
            Decimal(ecoule_jours) / Decimal(duree_totale_jours),
            Decimal('1'))
        ideal = (charge_totale * (Decimal('1') - fraction)).quantize(
            Decimal('0.01'))

        heures_cumulees += sum(
            (ts.heures for ts in timesheets if ts.date == courant),
            Decimal('0'))

        points.append({
            'date': courant.isoformat(),
            'charge_restante': restant,
            'charge_ideale': ideal,
            'heures_loguees_cumulees': heures_cumulees,
        })
        courant = courant + timedelta(weeks=1)

    return {'points': points, 'charge_totale': charge_totale}


# ── Tableau de bord portefeuille (PROJ36) ────────────────────────────────────
def tableau_portefeuille(company, statut=None, seuil_jours=None):
    """Tableau de bord PORTEFEUILLE de la société (PROJ36) — interne/admin.

    Agrège, pour CHAQUE projet de la société (filtrable par ``statut``) :
    l'avancement physique (PROJ9), le nombre de tâches/jalons EN RETARD et À
    RISQUE (PROJ14, horizon ``seuil_jours``), la marge réelle (P&L PROJ26) et la
    charge totale (somme des ``charge_estimee`` des tâches). Renvoie une ligne par
    projet + des totaux portefeuille (nb projets, retards/risques cumulés, marge
    réelle cumulée, charge totale). Donnée 100 % INTERNE de pilotage — jamais
    exposée au client. Tout est scopé société. Lecture seule (aucune écriture).
    """
    projets = Projet.objects.filter(company=company).select_related(
        'evaluation')
    if statut:
        projets = projets.filter(statut=statut)
    projets = projets.order_by('-id')

    lignes = []
    total_marge_reelle = Decimal('0')
    total_charge = Decimal('0')
    total_retards = 0
    total_risques = 0
    notes_satisfaction = []
    for projet in projets:
        avancement = rollup_avancement(projet)
        retards = retards_projet(projet, seuil_jours=seuil_jours)
        pnl = pnl_projet(company, projet)
        charge = Tache.objects.filter(
            projet=projet, company=company,
            charge_estimee__isnull=False).aggregate(
                s=Sum('charge_estimee'))['s'] or Decimal('0')

        nb_retards = (
            retards['nb_taches_en_retard']
            + retards['nb_jalons_en_retard'])
        nb_risques = (
            retards['nb_taches_a_risque']
            + retards['nb_jalons_a_risque'])

        total_marge_reelle += pnl['marge_reelle']
        total_charge += charge
        total_retards += nb_retards
        total_risques += nb_risques

        # Dernière santé RAG du projet (XPRJ15) — None si aucun point saisi.
        dernier_point = PointAvancement.objects.filter(
            company=company, projet=projet).order_by(
                '-date_point', '-id').first()

        # Note CSAT client (ZPRJ7) — None tant qu'aucune évaluation n'a été
        # soumise (le lien peut exister sans dépôt).
        evaluation = getattr(projet, 'evaluation', None)
        note_satisfaction = (
            evaluation.note
            if evaluation is not None and evaluation.note is not None
            else None)
        if note_satisfaction is not None:
            notes_satisfaction.append(note_satisfaction)

        lignes.append({
            'projet_id': projet.id,
            'code': projet.code,
            'nom': projet.nom,
            'statut': projet.statut,
            'avancement_pct': avancement['avancement_pct'],
            'nb_retards': nb_retards,
            'nb_risques': nb_risques,
            'marge_reelle': pnl['marge_reelle'],
            'charge_totale': charge,
            'derniere_sante': (
                dernier_point.sante if dernier_point else None),
            'note_satisfaction': note_satisfaction,
            'politique_facturation': projet.politique_facturation,
        })

    note_satisfaction_moyenne = (
        round(sum(notes_satisfaction) / len(notes_satisfaction), 2)
        if notes_satisfaction else None)

    return {
        'nb_projets': len(lignes),
        'total_marge_reelle': total_marge_reelle,
        'total_charge': total_charge,
        'total_retards': total_retards,
        'total_risques': total_risques,
        'note_satisfaction_moyenne': note_satisfaction_moyenne,
        'projets': lignes,
    }


# ── Portail d'avancement client (PROJ37) ─────────────────────────────────────
def portail_avancement_client(projet):
    """Avancement d'un projet pour le PORTAIL CLIENT (PROJ37) — SANS coûts.

    Renvoie une vue STRICTEMENT NON FINANCIÈRE de l'avancement, destinée à un
    lien public client : avancement physique global (PROJ9), phases (libellé /
    statut / avancement / dates prévues-réelles) et jalons (libellé / date /
    statut). AUCUNE donnée interne ne traverse cette frontière :
        • PAS de budget, coût, marge, P&L, criticité de risque ;
        • PAS de ``facturation_pct`` des jalons (échéancier de paiement interne) ;
        • PAS de ``charge_estimee`` ni de coût horaire.

    La société est portée par le projet. Lecture seule (aucune écriture).
    """
    avancement = rollup_avancement(projet)

    phases = [
        {
            'libelle': p.libelle or p.get_type_phase_display(),
            'type_phase': p.type_phase,
            'statut': p.statut,
            'avancement_pct': int(p.avancement_pct),
            'date_debut_prevue': (
                p.date_debut_prevue.isoformat()
                if p.date_debut_prevue else None),
            'date_fin_prevue': (
                p.date_fin_prevue.isoformat()
                if p.date_fin_prevue else None),
            'date_debut_reelle': (
                p.date_debut_reelle.isoformat()
                if p.date_debut_reelle else None),
            'date_fin_reelle': (
                p.date_fin_reelle.isoformat()
                if p.date_fin_reelle else None),
        }
        for p in projet.phases.order_by('ordre', 'id')
    ]

    jalons = [
        {
            'libelle': j.libelle,
            'date_prevue': j.date_prevue.isoformat() if j.date_prevue else None,
            'date_reelle': j.date_reelle.isoformat() if j.date_reelle else None,
            'statut': j.statut,
        }
        for j in jalons_for_projet(projet)
    ]

    return {
        'projet': {
            'code': projet.code,
            'nom': projet.nom,
            'statut': projet.statut,
            'date_debut': (
                projet.date_debut.isoformat() if projet.date_debut else None),
            'date_fin_prevue': (
                projet.date_fin_prevue.isoformat()
                if projet.date_fin_prevue else None),
        },
        'avancement_pct': avancement['avancement_pct'],
        'phases': phases,
        'jalons': jalons,
    }


def _urgence_key(tache, aujourd_hui):
    """Clé de tri d'urgence : retard > échéance proche > priorité > id.

    Plus petite valeur = plus urgent. Une tâche sans ``date_fin_prevue`` est
    considérée la MOINS urgente sur l'axe date (mais reste triée par
    priorité). L'ordre de priorité est URGENTE < HAUTE < NORMALE < BASSE
    (numériquement) pour un tri croissant naturel.
    """
    ordre_priorite = {
        Tache.Priorite.URGENTE: 0,
        Tache.Priorite.HAUTE: 1,
        Tache.Priorite.NORMALE: 2,
        Tache.Priorite.BASSE: 3,
    }
    if tache.date_fin_prevue is None:
        retard_jours = 0
        echeance_rank = 1  # après les tâches datées
        echeance_ordre = 0
    else:
        delta = (tache.date_fin_prevue - aujourd_hui).days
        retard_jours = min(delta, 0)  # négatif si en retard, 0 sinon
        echeance_rank = 0
        echeance_ordre = delta
    return (
        retard_jours,  # plus négatif (plus en retard) trie en premier
        echeance_rank,
        echeance_ordre,
        ordre_priorite.get(tache.priorite, 2),
        tache.id,
    )


def mes_taches(user, aujourd_hui=None):
    """Tâches NON TERMINÉES de TOUS les projets d'un utilisateur (XPRJ12).

    Un utilisateur voit UNIQUEMENT ses propres tâches : celles où il est
    ``assigne`` directement (XPRJ10) sur la tâche, OU celles où sa
    ``RessourceProfil`` liée (``user`` FK) est affectée via
    ``AffectationRessource`` — soit directement (``ressource``), soit via une
    ``Equipe`` dont il est membre. Isolation société garantie : les querysets
    sont TOUJOURS scopés à ``user.company``.

    Trie par urgence : retard d'abord, puis échéance proche, puis priorité.
    Renvoie une liste de dicts (projet/échéance/retard_jours inclus) — jamais
    d'objets ORM bruts, pour rester un sélecteur LECTURE SEULE stable.
    """
    if aujourd_hui is None:
        aujourd_hui = _date.today()
    company = user.company

    ressource_ids = list(
        RessourceProfil.objects.filter(
            company=company, user=user).values_list('id', flat=True))

    filtre = Q(assigne__user=user)
    if ressource_ids:
        equipe_ids = list(
            Equipe.objects.filter(
                company=company, membres__id__in=ressource_ids)
            .values_list('id', flat=True))
        affectation_filtre = Q(
            affectations__ressource_id__in=ressource_ids)
        if equipe_ids:
            affectation_filtre |= Q(
                affectations__equipe_id__in=equipe_ids)
        filtre |= affectation_filtre

    taches = (
        Tache.objects.filter(company=company)
        .exclude(statut=Tache.Statut.TERMINE)
        .filter(filtre)
        .select_related('projet', 'assigne')
        .distinct()
    )

    resultats = []
    for tache in taches:
        retard_jours = 0
        if tache.date_fin_prevue is not None:
            delta = (aujourd_hui - tache.date_fin_prevue).days
            retard_jours = max(delta, 0)
        resultats.append({
            'id': tache.id,
            'libelle': tache.libelle,
            'statut': tache.statut,
            'priorite': tache.priorite,
            'projet_id': tache.projet_id,
            'projet_code': tache.projet.code,
            'projet_nom': tache.projet.nom,
            'date_fin_prevue': (
                tache.date_fin_prevue.isoformat()
                if tache.date_fin_prevue else None),
            'retard_jours': retard_jours,
            '_urgence': _urgence_key(tache, aujourd_hui),
        })

    resultats.sort(key=lambda r: r['_urgence'])
    for r in resultats:
        del r['_urgence']
    return resultats


# ── Marché public : exposition aux pénalités de retard (XPRJ27) ─────────────
def penalites_retard(projet, date_reference=None):
    """Exposition COURANTE aux pénalités de retard d'un marché public (XPRJ27).

    Donnée INTERNE de pilotage — jamais dans un document client. Calcule le
    nombre de jours de DÉPASSEMENT du délai contractuel d'exécution
    (``delai_execution_jours`` compté depuis ``projet.date_debut``) à
    ``date_reference`` (défaut aujourd'hui), puis l'exposition brute :

        jours_depassement × (taux_penalite_retard / 1000) × montant_marche

    plafonnée à ``plafond_penalite_pct`` % du ``montant_marche`` quand ce
    plafond est renseigné. AVANT le délai (pas de dépassement) → exposition
    NULLE (jamais négative). Un projet sans champs marché-public renseignés
    (cas des projets PRIVÉS, majoritaires) renvoie une exposition nulle avec
    ``applicable=False`` — sans jamais lever d'erreur, pour rester appelable
    sans condition depuis n'importe quel projet. Le décompte DÉFINITIF reste à
    établir à la CLÔTURE du marché (ce sélecteur ne fige rien, lecture seule).

    Renvoie un dict ``{applicable, jours_depassement, taux_penalite_retard,
    montant_marche, plafond_penalite_pct, exposition_brute, plafond_montant,
    exposition, plafonnee, decompte_definitif_a_etablir}``.
    """
    if date_reference is None:
        date_reference = _date.today()

    applicable = bool(
        projet.numero_marche
        and projet.delai_execution_jours is not None
        and projet.taux_penalite_retard is not None
        and projet.montant_marche is not None
        and projet.date_debut is not None
    )
    if not applicable:
        return {
            'applicable': False,
            'jours_depassement': 0,
            'taux_penalite_retard': None,
            'montant_marche': None,
            'plafond_penalite_pct': None,
            'exposition_brute': Decimal('0'),
            'plafond_montant': None,
            'exposition': Decimal('0'),
            'plafonnee': False,
            'decompte_definitif_a_etablir': False,
        }

    date_limite = projet.date_debut + timedelta(
        days=projet.delai_execution_jours)
    jours_depassement = max((date_reference - date_limite).days, 0)

    taux = projet.taux_penalite_retard
    montant_marche = projet.montant_marche
    exposition_brute = (
        Decimal(jours_depassement) * (taux / Decimal('1000')) * montant_marche
    ).quantize(Decimal('0.01'))

    plafond_montant = None
    exposition = exposition_brute
    plafonnee = False
    if projet.plafond_penalite_pct is not None:
        plafond_montant = (
            montant_marche * projet.plafond_penalite_pct / Decimal('100')
        ).quantize(Decimal('0.01'))
        if exposition_brute > plafond_montant:
            exposition = plafond_montant
            plafonnee = True

    return {
        'applicable': True,
        'jours_depassement': jours_depassement,
        'taux_penalite_retard': taux,
        'montant_marche': montant_marche,
        'plafond_penalite_pct': projet.plafond_penalite_pct,
        'exposition_brute': exposition_brute,
        'plafond_montant': plafond_montant,
        'exposition': exposition,
        'plafonnee': plafonnee,
        'decompte_definitif_a_etablir': jours_depassement > 0,
    }


def matrice_risques(projet):
    """Matrice des risques P × I (grille 5×5) d'un projet (ZPRJ8).

    Compte, par cellule ``(probabilite, impact)`` (1–5 chacun), les
    ``Risque`` du projet dont le ``statut`` est OUVERT ou SURVEILLÉ — les
    risques MAÎTRISÉS/CLOS sont EXCLUS de la grille (comptage courant, pas
    historique). Renvoie aussi le TOP risques par criticité décroissante
    (mêmes risques ouverts/surveillés) pour affichage à côté de la heatmap.

    Un projet sans risque ouvert/surveillé renvoie une grille entièrement à
    zéro et un top vide — jamais d'erreur.

    Renvoie un dict ``{grille: [{probabilite, impact, nombre}, ...25],
    total_ouverts_surveilles, top_risques: [{id, libelle, probabilite,
    impact, criticite, statut}, ...]}``.
    """
    risques_actifs = list(
        Risque.objects.filter(
            projet=projet,
            statut__in=[Risque.Statut.OUVERT, Risque.Statut.SURVEILLE],
        ).order_by('-criticite', '-id')
    )

    comptes = {}
    for r in risques_actifs:
        cle = (r.probabilite, r.impact)
        comptes[cle] = comptes.get(cle, 0) + 1

    grille = []
    for probabilite in range(1, 6):
        for impact in range(1, 6):
            grille.append({
                'probabilite': probabilite,
                'impact': impact,
                'nombre': comptes.get((probabilite, impact), 0),
            })

    top_risques = [
        {
            'id': r.id,
            'libelle': r.libelle,
            'probabilite': r.probabilite,
            'impact': r.impact,
            'criticite': r.criticite,
            'statut': r.statut,
        }
        for r in risques_actifs[:10]
    ]

    return {
        'grille': grille,
        'total_ouverts_surveilles': len(risques_actifs),
        'top_risques': top_risques,
    }


# ── ARC40 — provider KPI pour le reporting fédéré ────────────────────────────

def kpi_projets_par_statut(company):
    """ARC40 — tuiles KPI « projets par statut » pour le reporting fédéré.

    Déclaré dans ``apps/gestion_projet/platform.py`` (surface
    ``kpi_providers``) et résolu par ``apps/reporting/reports.py::kpi_federes``
    — le reporting n'importe JAMAIS les modèles projet, il appelle ce
    sélecteur (frontière inter-app). Une tuile par statut EFFECTIVEMENT
    présent (aucune tuile à zéro inventée). Forme normalisée
    ``{id, label, valeur, unite?}``. Lecture seule, scopé société.
    """
    from django.db.models import Count

    from .models import Projet

    labels = dict(Projet.Statut.choices)
    rows = (Projet.objects.filter(company=company)
            .values('statut').annotate(n=Count('id')).order_by('statut'))
    return [
        {'id': f"projets_{row['statut']}",
         'label': f"Projets — {labels.get(row['statut'], row['statut'])}",
         'valeur': row['n'], 'unite': 'projets'}
        for row in rows
    ]
