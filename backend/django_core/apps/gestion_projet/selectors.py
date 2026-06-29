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

from django.db.models import Q

from .models import (
    AffectationRessource,
    BaselinePlanning,
    CalendrierProjet,
    DependanceTache,
    Equipe,
    Indisponibilite,
    Jalon,
    ProjetLien,
    RessourceProfil,
    Tache,
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
# Heures travaillées par jour ouvré (capacité d'une ressource à plein temps).
_HEURES_PAR_JOUR_DEFAUT = 8


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


def plan_de_charge(company, debut, fin, heures_par_jour=_HEURES_PAR_JOUR_DEFAUT,
                   ressource_id=None):
    """Plan de charge d'une société sur [debut, fin] : capacité vs affecté.

    PROJ18 — pour CHAQUE ``RessourceProfil`` ACTIVE de la société (ou la seule
    ``ressource_id`` demandée), agrège :

    * ``capacite_heures`` — jours OUVRÉS (semaine L-V par défaut) de la fenêtre
      INCLUSIVE [debut, fin], MOINS les jours ouvrés couverts par une
      indisponibilité (congé/formation/arrêt) chevauchant la fenêtre, × le
      nombre d'heures par jour ouvré (``heures_par_jour``, défaut 8) ;
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
